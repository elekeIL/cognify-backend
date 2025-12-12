"""Theme schemas for API validation."""

from datetime import datetime

from pydantic import BaseModel


class ThemeBase(BaseModel):
    """Base theme schema."""
    name: str
    description: str | None = None
    order: int = 0


class ThemeResponse(ThemeBase):
    """Schema for theme response."""
    id: str
    document_id: str
    created_at: datetime

    class Config:
        from_attributes = True
