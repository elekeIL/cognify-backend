"""Lesson model for storing generated lessons."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import String, Text, Integer, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Lesson(Base):
    """Lesson model representing a generated lesson from a document."""

    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Foreign key to document
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # Lesson content
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)  # Short summary
    content: Mapped[str] = mapped_column(Text)  # Full lesson text (250-400 words)
    word_count: Mapped[int] = mapped_column(Integer)

    # Workplace-focused sections
    what_youll_learn: Mapped[str] = mapped_column(Text, nullable=True)
    key_takeaways: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array
    apply_at_work: Mapped[str] = mapped_column(Text, nullable=True)

    # Learning outcomes (JSON stored as text)
    learning_outcomes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Completed learning outcome IDs (JSON array stored as text)
    outcomes_completed: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="[]")

    # Audio
    audio_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    audio_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # in seconds

    # Progress tracking
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_percentage: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    audio_position: Mapped[int] = mapped_column(Integer, default=0)  # seconds
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

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

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="lesson",
    )

    def __repr__(self) -> str:
        return f"<Lesson(id={self.id}, title={self.title})>"
