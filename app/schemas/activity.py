"""Activity schemas for API validation."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

from app.models.activity import ActivityType


class ActivityResponse(BaseModel):
    """Schema for activity response."""
    id: str
    activity_type: ActivityType
    title: str
    description: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityListResponse(BaseModel):
    """Schema for paginated activity list response."""
    items: List[ActivityResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
