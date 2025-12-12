"""Dashboard schemas for API validation."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """Schema for dashboard statistics."""
    total_documents: int
    total_lessons: int
    completed_lessons: int
    total_learning_time_minutes: int
    documents_this_week: int
    lessons_completed_this_week: int
    current_streak_days: int
    average_completion_rate: float  # percentage
    # Learning outcomes stats
    total_learning_outcomes: int = 0
    completed_learning_outcomes: int = 0
    learning_outcomes_rate: float = 0.0  # percentage


class RecentDocument(BaseModel):
    """Schema for recent document in dashboard."""
    id: str
    ingestion_id: str
    title: str
    file_type: str
    status: str
    created_at: datetime
    has_lesson: bool


class RecentLesson(BaseModel):
    """Schema for recent lesson in dashboard."""
    id: str
    document_id: str
    title: str
    summary: str
    progress_percentage: float
    is_completed: bool
    created_at: datetime
    last_accessed_at: Optional[datetime] = None


class DashboardResponse(BaseModel):
    """Schema for full dashboard response."""
    stats: DashboardStats
    recent_documents: List[RecentDocument]
    recent_lessons: List[RecentLesson]
