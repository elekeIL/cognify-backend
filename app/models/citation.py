"""Citation model for storing source snippets."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Citation(Base):
    """Citation model representing a source snippet from the document."""

    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Foreign key to document
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )

    # Citation information
    snippet: Mapped[str] = mapped_column(Text)  # The actual quoted text
    location: Mapped[str] = mapped_column(String(100))  # e.g., "Page 5, Paragraph 2"
    relevance_score: Mapped[float] = mapped_column(Integer, default=0)  # 0-100
    order: Mapped[int] = mapped_column(Integer, default=0)

    # Context
    context_before: Mapped[str] = mapped_column(Text, nullable=True)
    context_after: Mapped[str] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="citations",
    )

    def __repr__(self) -> str:
        return f"<Citation(id={self.id}, location={self.location})>"
