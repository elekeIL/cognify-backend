"""Document model for storing uploaded files."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, Text, Integer, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.theme import Theme
    from app.models.lesson import Lesson
    from app.models.citation import Citation


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStep(str, Enum):
    """Individual processing steps."""
    EXTRACT_TEXT = "extract_text"
    EXTRACT_THEMES = "extract_themes"
    GENERATE_LESSON = "generate_lesson"
    EXTRACT_CITATIONS = "extract_citations"
    GENERATE_AUDIO = "generate_audio"


class StepStatus(str, Enum):
    """Status for individual processing steps."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Ordered list of processing steps
PROCESSING_STEPS_ORDER = [
    ProcessingStep.EXTRACT_TEXT,
    ProcessingStep.EXTRACT_THEMES,
    ProcessingStep.GENERATE_LESSON,
    ProcessingStep.EXTRACT_CITATIONS,
    ProcessingStep.GENERATE_AUDIO,
]


class FileType(str, Enum):
    """Supported file types."""
    PDF = "PDF"
    DOCX = "DOCX"
    TXT = "TXT"


class Document(Base):
    """Document model representing an uploaded file."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    ingestion_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: f"ing_{uuid.uuid4().hex[:12]}",
    )

    # User relationship
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # File information
    title: Mapped[str] = mapped_column(String(255))
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[FileType] = mapped_column(SQLEnum(FileType))
    file_size: Mapped[int] = mapped_column(Integer)  # in bytes
    file_path: Mapped[str] = mapped_column(String(500))

    # Content
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus),
        default=DocumentStatus.PENDING,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Step-level processing status (JSON stored as TEXT)
    # Format: {"extract_text": "completed", "extract_themes": "in_progress", ...}
    current_step: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default=None,
    )
    step_statuses: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
    failed_step: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default=None,
    )
    step_error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="documents",
    )
    themes: Mapped[List["Theme"]] = relationship(
        "Theme",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    lesson: Mapped[Optional["Lesson"]] = relationship(
        "Lesson",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )
    citations: Mapped[List["Citation"]] = relationship(
        "Citation",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title}, status={self.status})>"
