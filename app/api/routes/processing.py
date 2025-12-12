"""Document processing endpoints with step-by-step execution."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import DbSession, CurrentUser
from app.models.document import (
    DocumentStatus,
    ProcessingStep,
    StepStatus,
    PROCESSING_STEPS_ORDER,
)
from app.schemas.document import (
    ProcessingStatusResponse,
    StepRequest,
    StepResponse,
    RetryStepRequest,
    RetryStepResponse,
)
from app.services.document_service import DocumentService
from app.services.step_processor import StepProcessor
from app.services.activity_service import ActivityService

router = APIRouter()
logger = logging.getLogger(__name__)
document_service = DocumentService()
step_processor = StepProcessor()


def get_step_index(step: ProcessingStep) -> int:
    """Get the index of a step in the processing order."""
    try:
        return PROCESSING_STEPS_ORDER.index(step)
    except ValueError:
        return -1


def get_next_step(current_step: ProcessingStep) -> Optional[ProcessingStep]:
    """Get the next step after the current one."""
    idx = get_step_index(current_step)
    if idx >= 0 and idx < len(PROCESSING_STEPS_ORDER) - 1:
        return PROCESSING_STEPS_ORDER[idx + 1]
    return None


def calculate_progress(step_statuses: dict) -> int:
    """Calculate overall progress percentage based on step statuses."""
    if not step_statuses:
        return 0

    completed_steps = sum(
        1 for status in step_statuses.values()
        if status == StepStatus.COMPLETED.value
    )
    total_steps = len(PROCESSING_STEPS_ORDER)
    return int((completed_steps / total_steps) * 100)


@router.get("/{document_id}/processing-status", response_model=ProcessingStatusResponse)
async def get_processing_status(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get detailed processing status with step-level information.

    Returns the current state of each processing step, allowing
    the frontend to display granular progress information.
    """
    document = await document_service.get_document_by_id(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Parse step statuses from JSON
    step_statuses = {}
    if document.step_statuses:
        try:
            step_statuses = json.loads(document.step_statuses)
        except json.JSONDecodeError:
            step_statuses = {}

    # Determine if retry is available
    can_retry = (
        document.status == DocumentStatus.FAILED and
        document.failed_step is not None and
        document.retry_count < 3  # Max 3 retries
    )

    # Parse current and failed steps
    current_step = None
    failed_step = None

    if document.current_step:
        try:
            current_step = ProcessingStep(document.current_step)
        except ValueError:
            pass

    if document.failed_step:
        try:
            failed_step = ProcessingStep(document.failed_step)
        except ValueError:
            pass

    return ProcessingStatusResponse(
        id=document.id,
        ingestion_id=document.ingestion_id,
        status=document.status,
        current_step=current_step,
        failed_step=failed_step,
        step_statuses=step_statuses,
        error_message=document.step_error_message or document.error_message,
        progress_percentage=calculate_progress(step_statuses),
        can_retry=can_retry,
        retry_count=document.retry_count,
    )


@router.post("/{document_id}/process/extract-text", response_model=StepResponse)
async def process_extract_text(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
    request: StepRequest = StepRequest(),
):
    """
    Step 1: Extract text from the uploaded document.

    This is the first step in the processing pipeline.
    Must be called before any other processing steps.
    """
    return await _execute_step(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        step=ProcessingStep.EXTRACT_TEXT,
        idempotency_key=request.idempotency_key,
    )


@router.post("/{document_id}/process/extract-themes", response_model=StepResponse)
async def process_extract_themes(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
    request: StepRequest = StepRequest(),
):
    """
    Step 2: Extract themes using AI.

    Requires Step 1 (extract-text) to be completed first.
    Identifies 3-7 main themes from the document content.
    """
    return await _execute_step(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        step=ProcessingStep.EXTRACT_THEMES,
        idempotency_key=request.idempotency_key,
    )


@router.post("/{document_id}/process/generate-lesson", response_model=StepResponse)
async def process_generate_lesson(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
    request: StepRequest = StepRequest(),
):
    """
    Step 3: Generate lesson content using AI.

    Requires Step 2 (extract-themes) to be completed first.
    Creates a 250-400 word workplace-focused lesson.
    """
    return await _execute_step(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        step=ProcessingStep.GENERATE_LESSON,
        idempotency_key=request.idempotency_key,
    )


@router.post("/{document_id}/process/extract-citations", response_model=StepResponse)
async def process_extract_citations(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
    request: StepRequest = StepRequest(),
):
    """
    Step 4: Extract citations from the document.

    Requires Step 2 (extract-themes) to be completed first.
    Finds top 2-3 source snippets with references.
    """
    return await _execute_step(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        step=ProcessingStep.EXTRACT_CITATIONS,
        idempotency_key=request.idempotency_key,
    )


@router.post("/{document_id}/process/generate-audio", response_model=StepResponse)
async def process_generate_audio(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
    request: StepRequest = StepRequest(),
):
    """
    Step 5: Generate audio narration.

    Requires Step 3 (generate-lesson) to be completed first.
    Creates voice narration for the lesson content.
    """
    return await _execute_step(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        step=ProcessingStep.GENERATE_AUDIO,
        idempotency_key=request.idempotency_key,
    )


@router.post("/{document_id}/process/retry", response_model=RetryStepResponse)
async def retry_failed_step(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
    request: RetryStepRequest,
):
    """
    Retry a failed processing step.

    Can only retry the specific step that failed.
    Maximum 3 retry attempts per document.
    """
    document = await document_service.get_document_by_id(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Verify document is in failed state
    if document.status != DocumentStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document is not in a failed state. Nothing to retry.",
        )

    # Verify this is the failed step
    if document.failed_step != request.step.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry step '{request.step.value}'. "
                   f"The failed step is '{document.failed_step}'.",
        )

    # Check retry limit
    if document.retry_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum retry attempts (3) reached. Please re-upload the document.",
        )

    # Check idempotency
    if request.idempotency_key and document.idempotency_key == request.idempotency_key:
        # Same request, return current status without re-executing
        return RetryStepResponse(
            document_id=document.id,
            step=request.step,
            status=StepStatus.IN_PROGRESS,
            message="Retry already in progress (idempotent)",
            retry_count=document.retry_count,
        )

    try:
        # Reset the failed step status
        step_statuses = {}
        if document.step_statuses:
            step_statuses = json.loads(document.step_statuses)

        step_statuses[request.step.value] = StepStatus.IN_PROGRESS.value

        # Update document for retry
        document.status = DocumentStatus.PROCESSING
        document.current_step = request.step.value
        document.step_statuses = json.dumps(step_statuses)
        document.step_error_message = None
        document.retry_count += 1
        if request.idempotency_key:
            document.idempotency_key = request.idempotency_key

        await db.flush()

        logger.info(f"Retrying step {request.step.value} for document {document_id} "
                   f"(attempt {document.retry_count})")

        # Execute the step
        result = await step_processor.execute_step(db, document, request.step)

        await db.commit()

        return RetryStepResponse(
            document_id=document.id,
            step=request.step,
            status=StepStatus.COMPLETED if result.success else StepStatus.FAILED,
            message=result.message,
            retry_count=document.retry_count,
            error_message=result.error_message,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Error retrying step {request.step.value} for document {document_id}: {e}")

        # Re-fetch document after rollback to update failure status
        try:
            document = await document_service.get_document_by_id(
                db=db,
                document_id=document_id,
                user_id=current_user.id,
            )
            if document:
                step_statuses = {}
                if document.step_statuses:
                    try:
                        step_statuses = json.loads(document.step_statuses)
                    except json.JSONDecodeError:
                        step_statuses = {}

                document.status = DocumentStatus.FAILED
                document.step_error_message = str(e)
                step_statuses[request.step.value] = StepStatus.FAILED.value
                document.step_statuses = json.dumps(step_statuses)
                await db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update document failure status: {update_error}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry step: {str(e)}",
        )


async def _execute_step(
    db: DbSession,
    document_id: str,
    user_id: str,
    step: ProcessingStep,
    idempotency_key: Optional[str] = None,
) -> StepResponse:
    """
    Internal function to execute a single processing step.

    Handles:
    - Document validation
    - Prerequisite step validation
    - Idempotency checking
    - Step execution
    - Status updates
    - Error handling
    """
    document = await document_service.get_document_by_id(
        db=db,
        document_id=document_id,
        user_id=user_id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Parse current step statuses
    step_statuses = {}
    if document.step_statuses:
        try:
            step_statuses = json.loads(document.step_statuses)
        except json.JSONDecodeError:
            step_statuses = {}

    # Check if step is already completed (idempotency)
    current_status = step_statuses.get(step.value)
    if current_status == StepStatus.COMPLETED.value:
        next_step = get_next_step(step)
        return StepResponse(
            document_id=document.id,
            step=step,
            status=StepStatus.COMPLETED,
            message=f"Step '{step.value}' already completed",
            next_step=next_step,
        )

    # Check if already in progress with same idempotency key
    if (
        idempotency_key and
        document.idempotency_key == idempotency_key and
        current_status == StepStatus.IN_PROGRESS.value
    ):
        return StepResponse(
            document_id=document.id,
            step=step,
            status=StepStatus.IN_PROGRESS,
            message=f"Step '{step.value}' already in progress (idempotent)",
        )

    # If step previously failed, this is a retry - increment retry count
    is_retry = current_status == StepStatus.FAILED.value or document.failed_step == step.value
    if is_retry:
        if document.retry_count >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum retry attempts (3) reached. Please re-upload the document.",
            )
        document.retry_count += 1
        logger.info(f"Retrying step {step.value} for document {document_id} (attempt {document.retry_count})")

    # Validate prerequisites
    step_idx = get_step_index(step)
    if step_idx > 0:
        prerequisite_step = PROCESSING_STEPS_ORDER[step_idx - 1]
        prereq_status = step_statuses.get(prerequisite_step.value)

        if prereq_status != StepStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot execute step '{step.value}'. "
                       f"Prerequisite step '{prerequisite_step.value}' "
                       f"must be completed first (current status: {prereq_status or 'not started'}).",
            )

    # Check if document is in a valid state for processing
    if document.status == DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document processing is already complete.",
        )

    try:
        # Update status to processing this step
        document.status = DocumentStatus.PROCESSING
        document.current_step = step.value
        document.failed_step = None
        document.step_error_message = None
        if idempotency_key:
            document.idempotency_key = idempotency_key

        step_statuses[step.value] = StepStatus.IN_PROGRESS.value
        document.step_statuses = json.dumps(step_statuses)

        await db.flush()

        logger.info(f"Starting step {step.value} for document {document_id}")

        # Execute the step
        result = await step_processor.execute_step(db, document, step)

        if result.success:
            # Mark step as completed
            step_statuses[step.value] = StepStatus.COMPLETED.value
            document.step_statuses = json.dumps(step_statuses)
            document.current_step = None

            # Check if all steps are complete
            all_complete = all(
                step_statuses.get(s.value) == StepStatus.COMPLETED.value
                for s in PROCESSING_STEPS_ORDER
            )

            if all_complete:
                document.status = DocumentStatus.COMPLETED
                from datetime import datetime, timezone
                document.processed_at = datetime.now(timezone.utc)
                logger.info(f"Document {document_id} processing completed")

                # Log document processed activity
                await ActivityService.log_document_processed(
                    db=db,
                    user_id=user_id,
                    document_id=document.id,
                    document_title=document.title,
                )

            await db.commit()

            next_step = get_next_step(step)
            return StepResponse(
                document_id=document.id,
                step=step,
                status=StepStatus.COMPLETED,
                message=result.message,
                next_step=next_step,
                retry_count=document.retry_count,
            )
        else:
            # Mark step as failed
            step_statuses[step.value] = StepStatus.FAILED.value
            document.step_statuses = json.dumps(step_statuses)
            document.status = DocumentStatus.FAILED
            document.failed_step = step.value
            document.step_error_message = result.error_message
            document.error_message = f"Processing failed at step: {step.value}"

            # Log processing failure activity
            await ActivityService.log_processing_failed(
                db=db,
                user_id=user_id,
                document_id=document.id,
                document_title=document.title,
                step=step.value,
                error_message=result.error_message or "Unknown error",
            )

            await db.commit()

            logger.error(f"Step {step.value} failed for document {document_id}: {result.error_message}")

            return StepResponse(
                document_id=document.id,
                step=step,
                status=StepStatus.FAILED,
                message=f"Step '{step.value}' failed",
                error_message=result.error_message,
                can_retry=document.retry_count < 3,
                retry_count=document.retry_count,
            )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()

        logger.error(f"Error executing step {step.value} for document {document_id}: {e}")

        # Re-fetch document after rollback to update failure status
        try:
            document = await document_service.get_document_by_id(
                db=db,
                document_id=document_id,
                user_id=user_id,
            )
            if document:
                # Parse existing step statuses
                step_statuses = {}
                if document.step_statuses:
                    try:
                        step_statuses = json.loads(document.step_statuses)
                    except json.JSONDecodeError:
                        step_statuses = {}

                # Update failure status
                step_statuses[step.value] = StepStatus.FAILED.value
                document.step_statuses = json.dumps(step_statuses)
                document.status = DocumentStatus.FAILED
                document.failed_step = step.value
                document.step_error_message = str(e)
                document.error_message = f"Processing failed at step: {step.value}"

                await db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update document failure status: {update_error}")

        # Get retry count from document if we have it
        current_retry_count = document.retry_count if document else 0

        return StepResponse(
            document_id=document_id,
            step=step,
            status=StepStatus.FAILED,
            message=f"Step '{step.value}' failed due to an error",
            error_message=str(e),
            can_retry=current_retry_count < 3,
            retry_count=current_retry_count,
        )
