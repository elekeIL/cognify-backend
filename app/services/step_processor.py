"""Step processor service for executing individual processing steps."""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, ProcessingStep
from app.models.theme import Theme
from app.models.lesson import Lesson
from app.models.citation import Citation
from app.services.file_processor import FileProcessor
from app.services.ai_service import AIService
from app.services.audio_service import AudioService

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of executing a processing step."""
    success: bool
    message: str
    error_message: Optional[str] = None
    data: Optional[dict] = None


class StepProcessor:
    """Service for executing individual document processing steps."""

    def __init__(self):
        """Initialize step processor with required services."""
        self.file_processor = FileProcessor()
        self.ai_service = AIService()
        self.audio_service = AudioService()

    async def execute_step(
        self,
        db: AsyncSession,
        document: Document,
        step: ProcessingStep,
    ) -> StepResult:
        """
        Execute a specific processing step for a document.

        Args:
            db: Database session
            document: Document to process
            step: Step to execute

        Returns:
            StepResult with success status and message
        """
        step_handlers = {
            ProcessingStep.EXTRACT_TEXT: self._execute_extract_text,
            ProcessingStep.EXTRACT_THEMES: self._execute_extract_themes,
            ProcessingStep.GENERATE_LESSON: self._execute_generate_lesson,
            ProcessingStep.EXTRACT_CITATIONS: self._execute_extract_citations,
            ProcessingStep.GENERATE_AUDIO: self._execute_generate_audio,
        }

        handler = step_handlers.get(step)
        if not handler:
            return StepResult(
                success=False,
                message=f"Unknown step: {step.value}",
                error_message=f"No handler found for step '{step.value}'",
            )

        try:
            logger.info(f"Executing step '{step.value}' for document {document.id}")
            result = await handler(db, document)
            if result.success:
                logger.info(f"Step '{step.value}' completed successfully for document {document.id}")
            else:
                logger.warning(f"Step '{step.value}' failed for document {document.id}: {result.error_message}")
            return result
        except Exception as e:
            logger.error(f"Error in step '{step.value}' for document {document.id}: {e}")
            return StepResult(
                success=False,
                message=f"Error executing step '{step.value}'",
                error_message=str(e),
            )

    async def _execute_extract_text(
        self,
        db: AsyncSession,
        document: Document,
    ) -> StepResult:
        """
        Step 1: Extract text content from the uploaded document.

        Reads the file and extracts all text content, storing it
        in the document's raw_content field.
        """
        try:
            # Extract text from file
            text_content, word_count = await FileProcessor.extract_text(
                document.file_path, document.file_type
            )

            if not text_content or not text_content.strip():
                return StepResult(
                    success=False,
                    message="No text content could be extracted from the document",
                    error_message="The document appears to be empty or contains no extractable text",
                )

            # Update document with extracted content
            document.raw_content = text_content
            document.word_count = word_count

            await db.flush()

            return StepResult(
                success=True,
                message=f"Successfully extracted {word_count} words from document",
                data={"word_count": word_count},
            )

        except FileNotFoundError:
            return StepResult(
                success=False,
                message="Document file not found",
                error_message="The uploaded file could not be located on the server",
            )
        except Exception as e:
            return StepResult(
                success=False,
                message="Failed to extract text from document",
                error_message=str(e),
            )

    async def _execute_extract_themes(
        self,
        db: AsyncSession,
        document: Document,
    ) -> StepResult:
        """
        Step 2: Extract themes from the document content using AI.

        Analyzes the text content to identify 3-7 main themes
        and stores them in the database.
        """
        try:
            if not document.raw_content:
                return StepResult(
                    success=False,
                    message="No text content available for theme extraction",
                    error_message="Step 1 (extract text) must be completed first",
                )

            # Extract themes using AI
            themes_data = await self.ai_service.extract_themes(document.raw_content)

            if not themes_data:
                return StepResult(
                    success=False,
                    message="No themes could be extracted from the document",
                    error_message="AI analysis did not return any themes",
                )

            # Clear existing themes (for retry scenarios)
            await db.execute(
                delete(Theme).where(Theme.document_id == document.id)
            )
            await db.flush()

            # Create theme records
            for idx, theme_data in enumerate(themes_data):
                # Handle both dict and Pydantic model objects
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

            # Convert themes to serializable format for response
            themes_serializable = [
                {"name": t.name if hasattr(t, 'name') else t.get("name"),
                 "description": t.description if hasattr(t, 'description') else t.get("description", "")}
                for t in themes_data
            ]

            return StepResult(
                success=True,
                message=f"Successfully identified {len(themes_data)} themes",
                data={"themes_count": len(themes_data), "themes": themes_serializable},
            )

        except Exception as e:
            return StepResult(
                success=False,
                message="Failed to extract themes from document",
                error_message=str(e),
            )

    async def _execute_generate_lesson(
        self,
        db: AsyncSession,
        document: Document,
    ) -> StepResult:
        """
        Step 3: Generate lesson content using AI.

        Creates a 250-400 word workplace-focused lesson based on
        the document content and extracted themes.
        """
        try:
            if not document.raw_content:
                return StepResult(
                    success=False,
                    message="No text content available for lesson generation",
                    error_message="Step 1 (extract text) must be completed first",
                )

            # Get themes for lesson generation
            themes_query = select(Theme).where(Theme.document_id == document.id).order_by(Theme.order)
            result = await db.execute(themes_query)
            themes = result.scalars().all()

            if not themes:
                return StepResult(
                    success=False,
                    message="No themes available for lesson generation",
                    error_message="Step 2 (extract themes) must be completed first",
                )

            # Convert themes to dict format for AI service
            themes_data = [
                {"name": t.name, "description": t.description}
                for t in themes
            ]

            # Generate lesson using AI
            lesson_data = await self.ai_service.generate_lesson(
                document.raw_content, themes_data
            )

            if not lesson_data:
                return StepResult(
                    success=False,
                    message="Failed to generate lesson content",
                    error_message="AI did not return lesson data",
                )

            # Delete existing lesson if any (for retry scenarios)
            await db.execute(
                delete(Lesson).where(Lesson.document_id == document.id)
            )
            await db.flush()

            # Handle both dict and Pydantic model objects (LessonOutput)
            if hasattr(lesson_data, 'title'):
                # Pydantic model
                title = lesson_data.title
                summary = lesson_data.summary
                content = lesson_data.content
                what_youll_learn = lesson_data.what_youll_learn
                key_takeaways = lesson_data.key_takeaways
                apply_at_work = lesson_data.apply_at_work
                learning_outcomes = getattr(lesson_data, 'learning_outcomes', [])
            else:
                # Dict
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
                # Convert Pydantic models to dicts if needed
                learning_outcomes = json.dumps([
                    lo.model_dump() if hasattr(lo, 'model_dump') else lo
                    for lo in learning_outcomes
                ])

            # Create lesson record
            lesson = Lesson(
                document_id=document.id,
                title=title,
                summary=summary,
                content=content,
                word_count=len(content.split()),
                what_youll_learn=what_youll_learn,
                key_takeaways=key_takeaways,
                apply_at_work=apply_at_work,
                learning_outcomes=learning_outcomes,
            )
            db.add(lesson)

            await db.flush()

            return StepResult(
                success=True,
                message=f"Successfully generated lesson with {lesson.word_count} words",
                data={"lesson_title": lesson.title, "word_count": lesson.word_count},
            )

        except Exception as e:
            return StepResult(
                success=False,
                message="Failed to generate lesson",
                error_message=str(e),
            )

    async def _execute_extract_citations(
        self,
        db: AsyncSession,
        document: Document,
    ) -> StepResult:
        """
        Step 4: Extract citations from the document.

        Finds top 2-3 source snippets with references to support
        the lesson content.
        """
        try:
            if not document.raw_content:
                return StepResult(
                    success=False,
                    message="No text content available for citation extraction",
                    error_message="Step 1 (extract text) must be completed first",
                )

            # Get themes for context
            themes_query = select(Theme).where(Theme.document_id == document.id).order_by(Theme.order)
            result = await db.execute(themes_query)
            themes = result.scalars().all()

            themes_data = [
                {"name": t.name, "description": t.description}
                for t in themes
            ]

            # Extract citations using AI
            citations_data = await self.ai_service.extract_citations(
                document.raw_content, themes_data
            )

            # Handle empty citations (valid but log warning)
            if not citations_data:
                logger.warning(f"No citations extracted for document {document.id} - this may indicate low-quality source content")

            # Clear existing citations (for retry scenarios)
            await db.execute(
                delete(Citation).where(Citation.document_id == document.id)
            )
            await db.flush()

            # Create citation records
            for idx, citation_data in enumerate(citations_data):
                # Handle both dict and Pydantic model objects
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

            return StepResult(
                success=True,
                message=f"Successfully extracted {len(citations_data)} citations",
                data={"citations_count": len(citations_data)},
            )

        except Exception as e:
            return StepResult(
                success=False,
                message="Failed to extract citations",
                error_message=str(e),
            )

    async def _execute_generate_audio(
        self,
        db: AsyncSession,
        document: Document,
    ) -> StepResult:
        """
        Step 5: Generate audio narration for the lesson.

        Creates voice narration using text-to-speech for the
        lesson content.
        """
        try:
            # Get the lesson
            lesson_query = select(Lesson).where(Lesson.document_id == document.id)
            result = await db.execute(lesson_query)
            lesson = result.scalar_one_or_none()

            if not lesson:
                return StepResult(
                    success=False,
                    message="No lesson available for audio generation",
                    error_message="Step 3 (generate lesson) must be completed first",
                )

            # Validate lesson has content for audio
            if not lesson.content or not lesson.content.strip():
                return StepResult(
                    success=False,
                    message="Lesson content is empty",
                    error_message="Cannot generate audio for an empty lesson",
                )

            # Generate audio content
            audio_text = f"{lesson.title}. {lesson.content}"

            # Delete existing audio file if any (for retry scenarios)
            if lesson.audio_path:
                await self.audio_service.delete_audio(lesson.audio_path)

            # Generate new audio
            audio_path, audio_duration = await self.audio_service.generate_audio(audio_text)

            if not audio_path:
                return StepResult(
                    success=False,
                    message="Failed to generate audio file",
                    error_message="Audio service did not return a valid file path",
                )

            # Update lesson with audio info
            lesson.audio_path = audio_path
            lesson.audio_duration = audio_duration

            await db.flush()

            return StepResult(
                success=True,
                message=f"Successfully generated audio narration ({audio_duration:.1f} seconds)",
                data={"audio_duration": audio_duration, "audio_path": audio_path},
            )

        except Exception as e:
            return StepResult(
                success=False,
                message="Failed to generate audio",
                error_message=str(e),
            )
