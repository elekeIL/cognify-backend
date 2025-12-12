"""Notification schemas for API validation."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    """Schema for notification response."""
    id: str
    type: NotificationType
    title: str
    description: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action_url: Optional[str] = None
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schema for paginated notification list response."""
    items: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    total_pages: int


class NotificationCreate(BaseModel):
    """Schema for creating a notification (internal use)."""
    user_id: str
    type: NotificationType = NotificationType.INFO
    title: str
    description: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action_url: Optional[str] = None


class MarkReadRequest(BaseModel):
    """Schema for marking notifications as read."""
    notification_ids: List[str]


class UnreadCountResponse(BaseModel):
    """Schema for unread notification count."""
    unread_count: int
