"""Lesson endpoints."""

import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func

from app.core.dependencies import DbSession, CurrentUser
from app.models.document import Document, DocumentStatus
from app.models.lesson import Lesson
import json
from app.schemas.lesson import (
    LessonResponse,
    LessonWithAudioResponse,
    LessonProgressUpdate,
    LessonOutcomeUpdate,
    LessonListResponse,
)
from app.schemas.theme import ThemeResponse
from app.services.audio_service import AudioService
from app.services.activity_service import ActivityService

router = APIRouter()
audio_service = AudioService()


@router.get("", response_model=LessonListResponse)
async def list_lessons(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 10,
):
    """
    List all lessons for the current user with pagination.

    Returns lessons from successfully processed documents with themes.
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    # Count total lessons
    count_query = (
        select(func.count(Lesson.id))
        .join(Document)
        .where(Document.user_id == current_user.id)
        .where(Document.status == DocumentStatus.COMPLETED)
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated lessons with document relationship for themes
    query = (
        select(Lesson)
        .join(Document)
        .where(Document.user_id == current_user.id)
        .where(Document.status == DocumentStatus.COMPLETED)
        .order_by(Lesson.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    lessons = result.scalars().all()

    # Build response items
    items = []
    for lesson in lessons:
        # Fetch document with themes for this lesson
        doc_query = select(Document).where(Document.id == lesson.document_id)
        doc_result = await db.execute(doc_query)
        document = doc_result.scalar_one_or_none()

        items.append(LessonWithAudioResponse(
            id=lesson.id,
            document_id=lesson.document_id,
            title=lesson.title,
            summary=lesson.summary,
            content=lesson.content,
            word_count=lesson.word_count,
            what_youll_learn=lesson.what_youll_learn,
            key_takeaways=lesson.key_takeaways,
            apply_at_work=lesson.apply_at_work,
            learning_outcomes=lesson.learning_outcomes,
            audio_path=lesson.audio_path,
            audio_duration=lesson.audio_duration,
            audio_url=audio_service.get_audio_url(lesson.audio_path),
            is_completed=lesson.is_completed,
            progress_percentage=lesson.progress_percentage,
            audio_position=lesson.audio_position,
            time_spent_seconds=lesson.time_spent_seconds,
            outcomes_completed=lesson.outcomes_completed,
            completed_at=lesson.completed_at,
            last_accessed_at=lesson.last_accessed_at,
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        ))

    return LessonListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{lesson_id}", response_model=LessonWithAudioResponse)
async def get_lesson(
    lesson_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get a specific lesson by ID.

    Returns full lesson content including audio URL.
    """
    query = (
        select(Lesson)
        .join(Document)
        .where(Lesson.id == lesson_id)
        .where(Document.user_id == current_user.id)
    )

    result = await db.execute(query)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    return LessonWithAudioResponse(
        id=lesson.id,
        document_id=lesson.document_id,
        title=lesson.title,
        summary=lesson.summary,
        content=lesson.content,
        word_count=lesson.word_count,
        what_youll_learn=lesson.what_youll_learn,
        key_takeaways=lesson.key_takeaways,
        apply_at_work=lesson.apply_at_work,
        learning_outcomes=lesson.learning_outcomes,
        outcomes_completed=lesson.outcomes_completed,
        is_completed=lesson.is_completed,
        progress_percentage=lesson.progress_percentage,
        audio_position=lesson.audio_position,
        time_spent_seconds=lesson.time_spent_seconds,
        completed_at=lesson.completed_at,
        last_accessed_at=lesson.last_accessed_at,
        audio_path=lesson.audio_path,
        audio_duration=lesson.audio_duration,
        audio_url=audio_service.get_audio_url(lesson.audio_path),
        created_at=lesson.created_at,
        updated_at=lesson.updated_at,
    )


@router.get("/document/{document_id}", response_model=LessonWithAudioResponse)
async def get_lesson_by_document(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get the lesson for a specific document.

    Returns the lesson associated with the given document ID.
    """
    query = (
        select(Lesson)
        .join(Document)
        .where(Lesson.document_id == document_id)
        .where(Document.user_id == current_user.id)
    )

    result = await db.execute(query)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found for this document",
        )

    # Log lesson started activity (only if this is the first access - progress is 0)
    if lesson.progress_percentage == 0 and not lesson.is_completed:
        await ActivityService.log_lesson_started(
            db=db,
            user_id=current_user.id,
            lesson_id=lesson.id,
            lesson_title=lesson.title,
            document_id=lesson.document_id,
        )

    # Update last accessed
    lesson.last_accessed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()

    return LessonWithAudioResponse(
        id=lesson.id,
        document_id=lesson.document_id,
        title=lesson.title,
        summary=lesson.summary,
        content=lesson.content,
        word_count=lesson.word_count,
        what_youll_learn=lesson.what_youll_learn,
        key_takeaways=lesson.key_takeaways,
        apply_at_work=lesson.apply_at_work,
        learning_outcomes=lesson.learning_outcomes,
        outcomes_completed=lesson.outcomes_completed,
        audio_path=lesson.audio_path,
        audio_duration=lesson.audio_duration,
        is_completed=lesson.is_completed,
        progress_percentage=lesson.progress_percentage,
        audio_position=lesson.audio_position,
        time_spent_seconds=lesson.time_spent_seconds,
        completed_at=lesson.completed_at,
        last_accessed_at=lesson.last_accessed_at,
        audio_url=audio_service.get_audio_url(lesson.audio_path),
        created_at=lesson.created_at,
        updated_at=lesson.updated_at,
    )


@router.patch("/{lesson_id}/progress", response_model=LessonWithAudioResponse)
async def update_lesson_progress(
    lesson_id: str,
    progress_data: LessonProgressUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Update lesson progress.

    Track audio position, percentage complete, and time spent.
    """
    query = (
        select(Lesson)
        .join(Document)
        .where(Lesson.id == lesson_id)
        .where(Document.user_id == current_user.id)
    )

    result = await db.execute(query)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    # Update progress fields
    if progress_data.progress_percentage is not None:
        lesson.progress_percentage = min(progress_data.progress_percentage, 100.0)
    if progress_data.audio_position is not None:
        lesson.audio_position = progress_data.audio_position
    if progress_data.time_spent_seconds is not None:
        lesson.time_spent_seconds += progress_data.time_spent_seconds

    lesson.last_accessed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(lesson)

    return LessonWithAudioResponse(
        id=lesson.id,
        document_id=lesson.document_id,
        title=lesson.title,
        summary=lesson.summary,
        content=lesson.content,
        word_count=lesson.word_count,
        what_youll_learn=lesson.what_youll_learn,
        key_takeaways=lesson.key_takeaways,
        apply_at_work=lesson.apply_at_work,
        learning_outcomes=lesson.learning_outcomes,
        outcomes_completed=lesson.outcomes_completed,
        audio_path=lesson.audio_path,
        audio_duration=lesson.audio_duration,
        is_completed=lesson.is_completed,
        progress_percentage=lesson.progress_percentage,
        audio_position=lesson.audio_position,
        time_spent_seconds=lesson.time_spent_seconds,
        completed_at=lesson.completed_at,
        last_accessed_at=lesson.last_accessed_at,
        audio_url=audio_service.get_audio_url(lesson.audio_path),
        created_at=lesson.created_at,
        updated_at=lesson.updated_at,
    )


@router.post("/{lesson_id}/complete", response_model=LessonWithAudioResponse)
async def mark_lesson_complete(
    lesson_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Mark a lesson as completed.

    Sets is_completed to true and records completion timestamp.
    """
    query = (
        select(Lesson)
        .join(Document)
        .where(Lesson.id == lesson_id)
        .where(Document.user_id == current_user.id)
    )

    result = await db.execute(query)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    lesson.is_completed = True
    lesson.progress_percentage = 100.0
    lesson.completed_at = datetime.now(timezone.utc)
    lesson.last_accessed_at = datetime.now(timezone.utc)

    # Mark all learning outcomes as completed
    try:
        outcomes = json.loads(lesson.learning_outcomes or "[]")
        if outcomes:
            # Extract IDs from learning outcomes - they come from AI as objects with "id" field
            # Format is typically "lo1", "lo2", etc. (1-indexed from AI)
            all_completed = []
            for i, outcome in enumerate(outcomes):
                if isinstance(outcome, dict) and 'id' in outcome:
                    all_completed.append(outcome['id'])
                else:
                    # Fallback for string format - use 0-indexed to match frontend parsing
                    all_completed.append(f"lo{i}")
            lesson.outcomes_completed = json.dumps(all_completed)
    except json.JSONDecodeError:
        pass

    # Log lesson completed activity
    await ActivityService.log_lesson_completed(
        db=db,
        user_id=current_user.id,
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        document_id=lesson.document_id,
    )

    await db.flush()
    await db.refresh(lesson)
    await db.commit()

    return LessonWithAudioResponse(
        id=lesson.id,
        document_id=lesson.document_id,
        title=lesson.title,
        summary=lesson.summary,
        content=lesson.content,
        word_count=lesson.word_count,
        what_youll_learn=lesson.what_youll_learn,
        key_takeaways=lesson.key_takeaways,
        apply_at_work=lesson.apply_at_work,
        learning_outcomes=lesson.learning_outcomes,
        outcomes_completed=lesson.outcomes_completed,
        audio_path=lesson.audio_path,
        audio_duration=lesson.audio_duration,
        is_completed=lesson.is_completed,
        progress_percentage=lesson.progress_percentage,
        audio_position=lesson.audio_position,
        time_spent_seconds=lesson.time_spent_seconds,
        completed_at=lesson.completed_at,
        last_accessed_at=lesson.last_accessed_at,
        audio_url=audio_service.get_audio_url(lesson.audio_path),
        created_at=lesson.created_at,
        updated_at=lesson.updated_at,
    )


@router.post("/{lesson_id}/reset-progress", response_model=LessonWithAudioResponse)
async def reset_lesson_progress(
    lesson_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Reset lesson progress.

    Resets all progress tracking fields to initial values.
    """
    query = (
        select(Lesson)
        .join(Document)
        .where(Lesson.id == lesson_id)
        .where(Document.user_id == current_user.id)
    )

    result = await db.execute(query)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    lesson.is_completed = False
    lesson.progress_percentage = 0.0
    lesson.audio_position = 0
    lesson.completed_at = None
    # Reset all learning outcomes
    lesson.outcomes_completed = json.dumps([])

    await db.flush()
    await db.refresh(lesson)

    return LessonWithAudioResponse(
        id=lesson.id,
        document_id=lesson.document_id,
        title=lesson.title,
        summary=lesson.summary,
        content=lesson.content,
        word_count=lesson.word_count,
        what_youll_learn=lesson.what_youll_learn,
        key_takeaways=lesson.key_takeaways,
        apply_at_work=lesson.apply_at_work,
        learning_outcomes=lesson.learning_outcomes,
        outcomes_completed=lesson.outcomes_completed,
        audio_path=lesson.audio_path,
        audio_duration=lesson.audio_duration,
        is_completed=lesson.is_completed,
        progress_percentage=lesson.progress_percentage,
        audio_position=lesson.audio_position,
        time_spent_seconds=lesson.time_spent_seconds,
        completed_at=lesson.completed_at,
        last_accessed_at=lesson.last_accessed_at,
        audio_url=audio_service.get_audio_url(lesson.audio_path),
        created_at=lesson.created_at,
        updated_at=lesson.updated_at,
    )


@router.patch("/{lesson_id}/outcomes", response_model=LessonWithAudioResponse)
async def update_lesson_outcome(
    lesson_id: str,
    outcome_data: LessonOutcomeUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Toggle a learning outcome as completed or not.

    Updates the outcomes_completed array for the lesson.
    """
    query = (
        select(Lesson)
        .join(Document)
        .where(Lesson.id == lesson_id)
        .where(Document.user_id == current_user.id)
    )

    result = await db.execute(query)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    # Parse current completed outcomes
    try:
        completed = json.loads(lesson.outcomes_completed or "[]")
    except json.JSONDecodeError:
        completed = []

    # Update completion status
    if outcome_data.completed:
        if outcome_data.outcome_id not in completed:
            completed.append(outcome_data.outcome_id)
    else:
        if outcome_data.outcome_id in completed:
            completed.remove(outcome_data.outcome_id)

    lesson.outcomes_completed = json.dumps(completed)

    # Calculate progress based on outcomes completion
    try:
        outcomes = json.loads(lesson.learning_outcomes or "[]")
        if outcomes:
            lesson.progress_percentage = min((len(completed) / len(outcomes)) * 100, 100.0)
            # Auto-complete lesson if all outcomes are done
            if len(completed) >= len(outcomes) and not lesson.is_completed:
                lesson.is_completed = True
                lesson.completed_at = datetime.now(timezone.utc)
                # Log lesson completed activity
                await ActivityService.log_lesson_completed(
                    db=db,
                    user_id=current_user.id,
                    lesson_id=lesson.id,
                    lesson_title=lesson.title,
                    document_id=lesson.document_id,
                )
    except json.JSONDecodeError:
        pass

    lesson.last_accessed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(lesson)

    return LessonWithAudioResponse(
        id=lesson.id,
        document_id=lesson.document_id,
        title=lesson.title,
        summary=lesson.summary,
        content=lesson.content,
        word_count=lesson.word_count,
        what_youll_learn=lesson.what_youll_learn,
        key_takeaways=lesson.key_takeaways,
        apply_at_work=lesson.apply_at_work,
        learning_outcomes=lesson.learning_outcomes,
        outcomes_completed=lesson.outcomes_completed,
        audio_path=lesson.audio_path,
        audio_duration=lesson.audio_duration,
        is_completed=lesson.is_completed,
        progress_percentage=lesson.progress_percentage,
        audio_position=lesson.audio_position,
        time_spent_seconds=lesson.time_spent_seconds,
        completed_at=lesson.completed_at,
        last_accessed_at=lesson.last_accessed_at,
        audio_url=audio_service.get_audio_url(lesson.audio_path),
        created_at=lesson.created_at,
        updated_at=lesson.updated_at,
    )
