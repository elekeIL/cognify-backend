"""Citation schemas for API validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CitationBase(BaseModel):
    """Base citation schema."""
    snippet: str
    location: str
    relevance_score: float = 0
    order: int = 0
    context_before: Optional[str] = None
    context_after: Optional[str] = None


class CitationResponse(CitationBase):
    """Schema for citation response."""
    id: str
    document_id: str
    created_at: datetime

    class Config:
        from_attributes = True
