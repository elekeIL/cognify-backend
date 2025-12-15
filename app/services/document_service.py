"""Document service for managing document lifecycle and processing."""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import aiofiles
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

logger = logging.getLogger(__name__)

from app.models.document import Document, DocumentStatus, FileType
from app.models.theme import Theme
from app.models.lesson import Lesson
from app.models.citation import Citation
from app.services.file_processor import FileProcessor
from app.services.ai_service import AIService
from app.services.audio_service import AudioService

settings = get_settings()


class DocumentService:
    """Service for document management and processing."""

    def __init__(self):
        """Initialize document service."""
        self.file_processor = FileProcessor()
        self.ai_service = AIService()
        self.audio_service = AudioService()
        self.upload_dir = settings.upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    async def create_document(
        self,
        db: AsyncSession,
        user_id: str,
        file_name: str,
        file_content: bytes,
        title: Optional[str] = None,
    ) -> Document:
        """
        Create a new document from uploaded file.

        Args:
            db: Database session
            user_id: ID of the user uploading the document
            file_name: Original filename
            file_content: File content as bytes
            title: Optional custom title

        Returns:
            Created document
        """
        start_total = time.time()

        # Validate file type
        file_type = FileProcessor.get_file_type(file_name)

        # Save file to disk (async)
        file_id = uuid.uuid4().hex[:12]
        safe_filename = f"{file_id}_{file_name}"
        file_path = os.path.join(self.upload_dir, safe_filename)

        start = time.time()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)
        logger.info(f"[TIMING] File write: {time.time() - start:.2f}s ({len(file_content)/1024:.1f}KB)")

        # Create document record
        start = time.time()
        document = Document(
            user_id=user_id,
            title=title or self._generate_title_from_filename(file_name),
            file_name=file_name,
            file_type=file_type,
            file_size=len(file_content),
            file_path=file_path,
            status=DocumentStatus.PENDING,
        )

        db.add(document)
        await db.flush()
        await db.refresh(document)
        logger.info(f"[TIMING] DB insert: {time.time() - start:.2f}s")
        logger.info(f"[TIMING] Total upload: {time.time() - start_total:.2f}s")

        return document

    def _generate_title_from_filename(self, filename: str) -> str:
        """Generate a readable title from filename."""
        # Remove extension
        name = filename.rsplit(".", 1)[0]
        # Replace underscores and hyphens with spaces
        name = name.replace("_", " ").replace("-", " ")
        # Title case
        return name.title()

    async def process_document(self, db: AsyncSession, document_id: str) -> Document:
        """
        Process a document: extract text, themes, generate lesson and audio.

        Args:
            db: Database session
            document_id: ID of the document to process

        Returns:
            Processed document
        """
        # Get document
        document = await self.get_document_by_id(db, document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        try:
            # Update status to processing
            document.status = DocumentStatus.PROCESSING
            await db.flush()
            logger.info(f"Starting document processing: {document.id} ({document.file_name})")

            # Step 1: Extract text from file
            text_content, word_count = await FileProcessor.extract_text(
                document.file_path, document.file_type
            )
            document.raw_content = text_content
            document.word_count = word_count
            await db.flush()
            logger.info(f"Step 1 complete: Extracted {word_count} words")

            # Step 2: Extract themes using AI
            themes_data = await self.ai_service.extract_themes(text_content)

            for idx, theme_data in enumerate(themes_data):
                # Handle both Pydantic Theme objects and dicts
                if hasattr(theme_data, 'name'):
                    name = theme_data.name
                    description = theme_data.description
                else:
                    name = theme_data.get("name", f"Theme {idx + 1}")
                    description = theme_data.get("description", "")

                theme = Theme(
                    document_id=document.id,
                    name=name,
                    description=description,
                    order=idx,
                )
                db.add(theme)

            await db.flush()
            logger.info(f"Step 2 complete: Extracted {len(themes_data)} themes")

            # Convert themes to dict format for AI service
            themes_dict = [
                {"name": t.name if hasattr(t, 'name') else t.get("name"),
                 "description": t.description if hasattr(t, 'description') else t.get("description", "")}
                for t in themes_data
            ]

            # Step 3: Generate lesson using AI
            lesson_data = await self.ai_service.generate_lesson(text_content, themes_dict)

            # Handle both Pydantic LessonOutput objects and dicts
            if hasattr(lesson_data, 'title'):
                title = lesson_data.title
                summary = lesson_data.summary
                content = lesson_data.content
                what_youll_learn = lesson_data.what_youll_learn
                key_takeaways = lesson_data.key_takeaways
                apply_at_work = lesson_data.apply_at_work
                learning_outcomes = getattr(lesson_data, 'learning_outcomes', [])
            else:
                title = lesson_data.get("title", document.title)
                summary = lesson_data.get("summary", "")
                content = lesson_data.get("content", "")
                what_youll_learn = lesson_data.get("what_youll_learn", "")
                key_takeaways = lesson_data.get("key_takeaways", [])
                apply_at_work = lesson_data.get("apply_at_work", "")
                learning_outcomes = lesson_data.get("learning_outcomes", [])

            # Ensure key_takeaways is stored as JSON string
            if isinstance(key_takeaways, list):
                key_takeaways = json.dumps(key_takeaways)

            # Ensure learning_outcomes is stored as JSON string
            if isinstance(learning_outcomes, list):
                learning_outcomes = json.dumps([
                    lo.model_dump() if hasattr(lo, 'model_dump') else lo
                    for lo in learning_outcomes
                ])

            lesson = Lesson(
                document_id=document.id,
                title=title,
                summary=summary,
                content=content,
                word_count=len(content.split()),
                what_youll_learn=what_youll_learn,
                key_takeaways=key_takeaways,
                apply_at_work=apply_at_work,
                learning_outcomes=learning_outcomes if learning_outcomes else None,
            )
            db.add(lesson)
            await db.flush()
            logger.info(f"Step 3 complete: Generated lesson '{lesson.title}' ({lesson.word_count} words)")

            # Step 4: Extract citations
            citations_data = await self.ai_service.extract_citations(
                text_content, themes_dict
            )

            for idx, citation_data in enumerate(citations_data):
                # Handle both Pydantic Citation objects and dicts
                if hasattr(citation_data, 'snippet'):
                    snippet = citation_data.snippet
                    location = citation_data.location
                else:
                    snippet = citation_data.get("snippet", "")
                    location = citation_data.get("location", f"Section {idx + 1}")

                citation = Citation(
                    document_id=document.id,
                    snippet=snippet,
                    location=location,
                    relevance_score=80 - (idx * 10),  # Decreasing relevance
                    order=idx,
                )
                db.add(citation)

            await db.flush()
            logger.info(f"Step 4 complete: Extracted {len(citations_data)} citations")

            # Step 5: Generate audio narration
            audio_text = f"{lesson.title}. {lesson.content}"
            audio_path, audio_duration = await self.audio_service.generate_audio(audio_text)

            lesson.audio_path = audio_path
            lesson.audio_duration = audio_duration
            logger.info(f"Step 5 complete: Generated audio ({audio_duration:.1f}s)")

            # Mark as completed
            document.status = DocumentStatus.COMPLETED
            document.processed_at = datetime.now(timezone.utc)

            await db.flush()
            await db.refresh(document)

            logger.info(f"Document processing complete: {document.id}")
            return document

        except Exception as e:
            # Mark as failed
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)
            await db.flush()
            logger.error(f"Document processing failed: {document.id} - {e}")
            raise

    async def get_document_by_id(
        self,
        db: AsyncSession,
        document_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[Document]:
        """Get a document by ID, optionally filtering by user."""
        query = select(Document).where(Document.id == document_id)
        if user_id:
            query = query.where(Document.user_id == user_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_document_by_ingestion_id(
        self,
        db: AsyncSession,
        ingestion_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[Document]:
        """Get a document by ingestion ID, optionally filtering by user."""
        query = select(Document).where(Document.ingestion_id == ingestion_id)
        if user_id:
            query = query.where(Document.user_id == user_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_document_with_relations(
        self,
        db: AsyncSession,
        document_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[Document]:
        """Get a document with all relations loaded."""
        query = (
            select(Document)
            .where(Document.id == document_id)
            .options(
                selectinload(Document.themes),
                selectinload(Document.lesson),
                selectinload(Document.citations),
            )
        )
        if user_id:
            query = query.where(Document.user_id == user_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_documents(
            self,
            db: AsyncSession,
            user_id: str,
            page: int = 1,
            page_size: int = 10,
            status: Optional[DocumentStatus] = None,
    ) -> tuple[List[Document], int]:
        """
        Get paginated list of documents for a user.

        Returns:
            Tuple of (documents, total_count)
        """
        # Base query
        query = select(Document).where(Document.user_id == user_id)

        if status:
            query = query.where(Document.status == status)

        # Get total count - FIXED
        count_query = select(func.count(Document.id)).where(Document.user_id == user_id)
        if status:
            count_query = count_query.where(Document.status == status)

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        query = (
            query
            .order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(
                selectinload(Document.themes),
                selectinload(Document.lesson),
            )
        )

        result = await db.execute(query)
        documents = result.scalars().all()

        return list(documents), total

    async def delete_document(
        self,
        db: AsyncSession,
        document_id: str,
        user_id: str,
    ) -> bool:
        """Delete a document and all associated data."""
        document = await self.get_document_with_relations(db, document_id, user_id)
        if not document:
            return False

        # Delete files from disk
        if document.file_path and os.path.exists(document.file_path):
            os.remove(document.file_path)

        if document.lesson and document.lesson.audio_path:
            await self.audio_service.delete_audio(document.lesson.audio_path)

        # Delete from database (cascades to relations)
        await db.delete(document)
        await db.flush()

        return True
