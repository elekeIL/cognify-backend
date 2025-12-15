"""Global search endpoint."""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select, or_

from app.core.dependencies import DbSession, CurrentUser
from app.models.document import Document, DocumentStatus
from app.models.lesson import Lesson

router = APIRouter()


class SearchResult(BaseModel):
    """Unified search result item."""
    id: str
    type: str  # "document" or "lesson"
    title: str
    description: Optional[str] = None
    created_at: datetime
    relevance_score: float = 1.0
    # Additional fields for routing
    document_id: Optional[str] = None  # For lessons, this is used for navigation
    status: Optional[str] = None  # For documents
    is_completed: Optional[bool] = None  # For lessons


class SearchResponse(BaseModel):
    """Search response with unified results array."""
    query: str
    total: int
    results: List[SearchResult]


@router.get("", response_model=SearchResponse)
async def global_search(
    q: str,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 10,
):
    """
    Global search across documents and lessons.

    Searches document titles, filenames, and lesson titles/content.
    Returns a unified results array for easy frontend consumption.
    """
    if not q or len(q.strip()) < 2:
        return SearchResponse(
            query=q,
            total=0,
            results=[],
        )

    search_term = f"%{q.strip()}%"
    results: List[SearchResult] = []

    # Search documents
    doc_query = (
        select(Document)
        .where(Document.user_id == current_user.id)
        .where(
            or_(
                Document.title.ilike(search_term),
                Document.file_name.ilike(search_term),
            )
        )
        .order_by(Document.created_at.desc())
        .limit(limit)
    )

    doc_result = await db.execute(doc_query)
    documents = doc_result.scalars().all()

    for doc in documents:
        results.append(SearchResult(
            id=doc.id,
            type="document",
            title=doc.title,
            description=f"{doc.file_type.value.upper()} - {doc.file_size // 1024}KB",
            created_at=doc.created_at,
            relevance_score=1.0,
            document_id=doc.id,  # For documents, document_id equals id
            status=doc.status.value,
        ))

    # Search lessons
    lesson_query = (
        select(Lesson)
        .join(Document)
        .where(Document.user_id == current_user.id)
        .where(
            or_(
                Lesson.title.ilike(search_term),
                Lesson.summary.ilike(search_term),
                Lesson.content.ilike(search_term),
            )
        )
        .order_by(Lesson.created_at.desc())
        .limit(limit)
    )

    lesson_result = await db.execute(lesson_query)
    lessons = lesson_result.scalars().all()

    for lesson in lessons:
        summary = lesson.summary or ""
        description = summary[:100] + "..." if len(summary) > 100 else summary
        results.append(SearchResult(
            id=lesson.id,
            type="lesson",
            title=lesson.title,
            description=description,
            created_at=lesson.created_at,
            relevance_score=1.0,
            document_id=lesson.document_id,  # Important: used for /learning/{document_id} routing
            is_completed=lesson.is_completed,
        ))

    # Sort results by created_at (newest first)
    results.sort(key=lambda x: x.created_at, reverse=True)

    # Limit total results
    results = results[:limit]

    return SearchResponse(
        query=q,
        total=len(results),
        results=results,
    )
