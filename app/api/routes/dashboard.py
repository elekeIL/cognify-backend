"""Dashboard endpoints."""

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import select, func

from app.core.dependencies import DbSession, CurrentUser
from app.models.document import Document, DocumentStatus
from app.models.lesson import Lesson
from app.schemas.dashboard import (
    DashboardStats,
    RecentDocument,
    RecentLesson,
    DashboardResponse,
)

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get dashboard statistics for the current user.

    Returns counts, completion rates, and streak information.
    """
    # Get total documents count
    total_docs_result = await db.execute(
        select(func.count(Document.id)).where(Document.user_id == current_user.id)
    )
    total_documents = total_docs_result.scalar() or 0

    # Get total lessons count
    total_lessons_result = await db.execute(
        select(func.count(Lesson.id))
        .join(Document)
        .where(Document.user_id == current_user.id)
    )
    total_lessons = total_lessons_result.scalar() or 0

    # Get completed lessons count
    completed_lessons_result = await db.execute(
        select(func.count(Lesson.id))
        .join(Document)
        .where(Document.user_id == current_user.id)
        .where(Lesson.is_completed == True)
    )
    completed_lessons = completed_lessons_result.scalar() or 0

    # Get total learning time in minutes
    total_time_result = await db.execute(
        select(func.sum(Lesson.time_spent_seconds))
        .join(Document)
        .where(Document.user_id == current_user.id)
    )
    total_time_seconds = total_time_result.scalar() or 0
    total_learning_time_minutes = total_time_seconds // 60

    # Get documents this week
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    docs_this_week_result = await db.execute(
        select(func.count(Document.id))
        .where(Document.user_id == current_user.id)
        .where(Document.created_at >= week_ago)
    )
    documents_this_week = docs_this_week_result.scalar() or 0

    # Get lessons completed this week
    lessons_completed_week_result = await db.execute(
        select(func.count(Lesson.id))
        .join(Document)
        .where(Document.user_id == current_user.id)
        .where(Lesson.is_completed == True)
        .where(Lesson.completed_at >= week_ago)
    )
    lessons_completed_this_week = lessons_completed_week_result.scalar() or 0

    # Calculate average completion rate
    average_completion_rate = 0.0
    if total_lessons > 0:
        average_completion_rate = (completed_lessons / total_lessons) * 100

    # Calculate current streak (simplified - just count consecutive days with activity)
    current_streak_days = await _calculate_streak(db, current_user.id)

    # Calculate learning outcomes stats
    total_learning_outcomes = 0
    completed_learning_outcomes = 0

    lessons_query = (
        select(Lesson.learning_outcomes, Lesson.outcomes_completed)
        .join(Document)
        .where(Document.user_id == current_user.id)
    )
    lessons_result = await db.execute(lessons_query)
    for row in lessons_result.fetchall():
        try:
            outcomes = json.loads(row[0] or "[]")
            completed = json.loads(row[1] or "[]")
            total_learning_outcomes += len(outcomes)
            completed_learning_outcomes += len(completed)
        except (json.JSONDecodeError, TypeError):
            pass

    learning_outcomes_rate = 0.0
    if total_learning_outcomes > 0:
        learning_outcomes_rate = (completed_learning_outcomes / total_learning_outcomes) * 100

    return DashboardStats(
        total_documents=total_documents,
        total_lessons=total_lessons,
        completed_lessons=completed_lessons,
        total_learning_time_minutes=total_learning_time_minutes,
        documents_this_week=documents_this_week,
        lessons_completed_this_week=lessons_completed_this_week,
        current_streak_days=current_streak_days,
        average_completion_rate=round(average_completion_rate, 1),
        total_learning_outcomes=total_learning_outcomes,
        completed_learning_outcomes=completed_learning_outcomes,
        learning_outcomes_rate=round(learning_outcomes_rate, 1),
    )


@router.get("/recent-documents", response_model=list[RecentDocument])
async def get_recent_documents(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 5,
):
    """
    Get recent documents for the dashboard.

    Returns the most recently uploaded documents.
    """
    if limit < 1 or limit > 20:
        limit = 5

    query = (
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    documents = result.scalars().all()

    # Get lesson existence for each document
    doc_ids = [doc.id for doc in documents]
    if doc_ids:
        lesson_query = select(Lesson.document_id).where(Lesson.document_id.in_(doc_ids))
        lesson_result = await db.execute(lesson_query)
        docs_with_lessons = set(row[0] for row in lesson_result.fetchall())
    else:
        docs_with_lessons = set()

    return [
        RecentDocument(
            id=doc.id,
            ingestion_id=doc.ingestion_id,
            title=doc.title,
            file_type=doc.file_type.value,
            status=doc.status.value,
            created_at=doc.created_at,
            has_lesson=doc.id in docs_with_lessons,
        )
        for doc in documents
    ]


@router.get("/recent-lessons", response_model=list[RecentLesson])
async def get_recent_lessons(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 5,
):
    """
    Get recent lessons for the dashboard.

    Returns the most recently accessed or created lessons.
    """
    if limit < 1 or limit > 20:
        limit = 5

    query = (
        select(Lesson)
        .join(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Lesson.last_accessed_at.desc().nullsfirst(), Lesson.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    lessons = result.scalars().all()

    return [
        RecentLesson(
            id=lesson.id,
            document_id=lesson.document_id,
            title=lesson.title,
            summary=lesson.summary[:200] + "..." if len(lesson.summary) > 200 else lesson.summary,
            progress_percentage=lesson.progress_percentage,
            is_completed=lesson.is_completed,
            created_at=lesson.created_at,
            last_accessed_at=lesson.last_accessed_at,
        )
        for lesson in lessons
    ]


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get full dashboard data in a single request.

    Combines stats, recent documents, and recent lessons.
    """
    stats = await get_dashboard_stats(db, current_user)
    recent_documents = await get_recent_documents(db, current_user, limit=5)
    recent_lessons = await get_recent_lessons(db, current_user, limit=5)

    return DashboardResponse(
        stats=stats,
        recent_documents=recent_documents,
        recent_lessons=recent_lessons,
    )


async def _calculate_streak(db, user_id: str) -> int:
    """Calculate the current learning streak in days."""
    # Get distinct dates of lesson activity (last_accessed_at or completed_at)
    query = (
        select(func.date(Lesson.last_accessed_at))
        .join(Document)
        .where(Document.user_id == user_id)
        .where(Lesson.last_accessed_at.isnot(None))
        .distinct()
        .order_by(func.date(Lesson.last_accessed_at).desc())
    )

    result = await db.execute(query)
    dates = [row[0] for row in result.fetchall() if row[0] is not None]

    if not dates:
        return 0

    today = datetime.now(timezone.utc).date()
    streak = 0
    expected_date = today

    for activity_date in dates:
        if activity_date == expected_date:
            streak += 1
            expected_date -= timedelta(days=1)
        elif activity_date == expected_date - timedelta(days=1):
            # Allow for yesterday to continue the streak
            expected_date = activity_date
            streak += 1
            expected_date -= timedelta(days=1)
        else:
            break

    return streak
