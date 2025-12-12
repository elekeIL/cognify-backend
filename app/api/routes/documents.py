"""Document management endpoints."""

import math
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.dependencies import DbSession, CurrentUser
from app.models.document import DocumentStatus
from app.schemas.theme import ThemeResponse
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentDetailResponse,
    DocumentStatusResponse,
)
from app.services.document_service import DocumentService
from app.services.file_processor import FileProcessor
from app.services.activity_service import ActivityService

router = APIRouter()
settings = get_settings()
document_service = DocumentService()


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
):
    """
    Upload a document for processing.

    Supports PDF, DOCX, and TXT files.
    After upload, use the step-by-step processing endpoints to process the document:
    - POST /documents/{id}/process/extract-text
    - POST /documents/{id}/process/extract-themes
    - POST /documents/{id}/process/generate-lesson
    - POST /documents/{id}/process/extract-citations
    - POST /documents/{id}/process/generate-audio
    """
    # Validate file extension
    if not FileProcessor.validate_file_extension(
        file.filename, settings.allowed_extensions_list
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed types: {', '.join(settings.allowed_extensions_list)}",
        )

    # Read file content
    file_content = await file.read()

    # Check file size
    if len(file_content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB",
        )

    # Create document
    document = await document_service.create_document(
        db=db,
        user_id=current_user.id,
        file_name=file.filename,
        file_content=file_content,
        title=title,
    )

    # Note: Processing is no longer automatic.
    # Frontend should call the step-by-step processing endpoints.

    # Log document upload activity
    await ActivityService.log_document_uploaded(
        db=db,
        user_id=current_user.id,
        document_id=document.id,
        document_title=document.title,
    )
    await db.commit()

    return DocumentResponse(
        id=document.id,
        ingestion_id=document.ingestion_id,
        title=document.title,
        file_name=document.file_name,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        word_count=document.word_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
        processed_at=document.processed_at,
        themes_count=0,
        has_lesson=False,
    )


async def process_document_task(document_id: str):
    """Background task to process a document."""
    from app.db.session import async_session_maker

    async with async_session_maker() as db:
        try:
            await document_service.process_document(db, document_id)
            await db.commit()
        except Exception as e:
            await db.rollback()
            print(f"Error processing document {document_id}: {e}")


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 10,
    status: Optional[DocumentStatus] = None,
):
    """
    List all documents for the current user.

    Supports pagination and filtering by status.
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    documents, total = await document_service.get_user_documents(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
    )

    return DocumentListResponse(
        items=[
            DocumentResponse(
                id=doc.id,
                ingestion_id=doc.ingestion_id,
                title=doc.title,
                file_name=doc.file_name,
                file_type=doc.file_type,
                file_size=doc.file_size,
                status=doc.status,
                word_count=doc.word_count,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                processed_at=doc.processed_at,
                themes_count=len(doc.themes) if doc.themes else 0,
                themes=[ThemeResponse(id=t.id, name=t.name, description=t.description, order=t.order, document_id=t.document_id, created_at=t.created_at) for t in (doc.themes or [])],
                has_lesson=doc.lesson is not None if hasattr(doc, 'lesson') else False,
            )
            for doc in documents
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get detailed information about a specific document.

    Includes themes, lesson, and citations if available.
    """
    document = await document_service.get_document_with_relations(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get the processing status of a document.

    Useful for polling during background processing.
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

    # Calculate progress based on status
    progress_map = {
        DocumentStatus.PENDING: 0,
        DocumentStatus.PROCESSING: 50,
        DocumentStatus.COMPLETED: 100,
        DocumentStatus.FAILED: 0,
    }

    step_map = {
        DocumentStatus.PENDING: "Waiting in queue",
        DocumentStatus.PROCESSING: "Processing document",
        DocumentStatus.COMPLETED: "Complete",
        DocumentStatus.FAILED: "Failed",
    }

    return DocumentStatusResponse(
        id=document.id,
        ingestion_id=document.ingestion_id,
        status=document.status,
        progress=progress_map.get(document.status, 0),
        current_step=step_map.get(document.status, "Unknown"),
        error_message=document.error_message,
    )


@router.get("/ingestion/{ingestion_id}", response_model=DocumentDetailResponse)
async def get_document_by_ingestion_id(
    ingestion_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get a document by its ingestion ID.

    The ingestion_id is the public identifier for documents.
    """
    document = await document_service.get_document_by_ingestion_id(
        db=db,
        ingestion_id=ingestion_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Load relations
    document = await document_service.get_document_with_relations(
        db=db,
        document_id=document.id,
        user_id=current_user.id,
    )

    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Delete a document and all associated data.

    This action cannot be undone.
    """
    # Get document title before deletion for activity log
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

    document_title = document.title

    deleted = await document_service.delete_document(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Log document deletion activity
    await ActivityService.log_document_deleted(
        db=db,
        user_id=current_user.id,
        document_title=document_title,
    )
    await db.commit()


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Download the original uploaded document file.

    Returns the file for download.
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

    # Check if file exists
    if not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on server",
        )

    # Determine media type based on file extension
    media_type_map = {
        "PDF": "application/pdf",
        "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "TXT": "text/plain",
    }
    media_type = media_type_map.get(document.file_type.value, "application/octet-stream")

    return FileResponse(
        path=document.file_path,
        filename=document.file_name,
        media_type=media_type,
    )


@router.get("/recent", response_model=list[DocumentResponse])
async def get_recent_documents(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 5,
):
    """
    Get recent documents for the current user.

    Returns the most recently uploaded documents.
    """
    if limit < 1 or limit > 20:
        limit = 5

    documents, _ = await document_service.get_user_documents(
        db=db,
        user_id=current_user.id,
        page=1,
        page_size=limit,
        status=None,
    )

    return [
        DocumentResponse(
            id=doc.id,
            ingestion_id=doc.ingestion_id,
            title=doc.title,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status,
            word_count=doc.word_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            processed_at=doc.processed_at,
            themes_count=len(doc.themes) if doc.themes else 0,
                themes=[ThemeResponse(id=t.id, name=t.name, description=t.description, order=t.order, document_id=t.document_id, created_at=t.created_at) for t in (doc.themes or [])],
            has_lesson=doc.lesson is not None if hasattr(doc, 'lesson') else False,
        )
        for doc in documents
    ]
