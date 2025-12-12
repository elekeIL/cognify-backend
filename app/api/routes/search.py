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


class SearchResultDocument(BaseModel):
    """Search result for documents."""
    id: str
    type: str = "document"
    title: str
    description: Optional[str] = None
    status: str
    created_at: datetime


class SearchResultLesson(BaseModel):
    """Search result for lessons."""
    id: str
    type: str = "lesson"
    title: str
    description: Optional[str] = None
    document_id: str
    is_completed: bool
    created_at: datetime


class SearchResults(BaseModel):
    """Combined search results."""
    query: str
    total: int
    documents: List[SearchResultDocument]
    lessons: List[SearchResultLesson]


@router.get("", response_model=SearchResults)
async def global_search(
    q: str,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 10,
):
    """
    Global search across documents and lessons.

    Searches document titles, filenames, and lesson titles/content.
    """
    if not q or len(q.strip()) < 2:
        return SearchResults(
            query=q,
            total=0,
            documents=[],
            lessons=[],
        )

    search_term = f"%{q.strip()}%"

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

    return SearchResults(
        query=q,
        total=len(documents) + len(lessons),
        documents=[
            SearchResultDocument(
                id=doc.id,
                type="document",
                title=doc.title,
                description=f"{doc.file_type.value} - {doc.file_size // 1024}KB",
                status=doc.status.value,
                created_at=doc.created_at,
            )
            for doc in documents
        ],
        lessons=[
            SearchResultLesson(
                id=lesson.id,
                type="lesson",
                title=lesson.title,
                description=lesson.summary[:150] + "..." if len(lesson.summary) > 150 else lesson.summary,
                document_id=lesson.document_id,
                is_completed=lesson.is_completed,
                created_at=lesson.created_at,
            )
            for lesson in lessons
        ],
    )
