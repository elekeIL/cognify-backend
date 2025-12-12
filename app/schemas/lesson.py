"""Lesson schemas for API validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class LessonBase(BaseModel):
    """Base lesson schema."""
    title: str
    summary: str
    content: str
    word_count: int
    what_youll_learn: Optional[str] = None
    key_takeaways: Optional[str] = None  # JSON string of array
    apply_at_work: Optional[str] = None
    learning_outcomes: Optional[str] = None  # JSON string of array


class LessonResponse(LessonBase):
    """Schema for lesson response."""
    id: str
    document_id: str
    audio_path: Optional[str] = None
    audio_duration: Optional[float] = None  # Duration in seconds (can be fractional)
    is_completed: bool = False
    progress_percentage: float = 0.0
    audio_position: int = 0
    time_spent_seconds: int = 0
    outcomes_completed: Optional[str] = "[]"  # JSON string of completed outcome IDs
    completed_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LessonWithAudioResponse(LessonResponse):
    """Schema for lesson with audio URL."""
    audio_url: Optional[str] = None


class LessonProgressUpdate(BaseModel):
    """Schema for updating lesson progress."""
    progress_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    audio_position: Optional[int] = Field(None, ge=0)
    time_spent_seconds: Optional[int] = Field(None, ge=0)


class LessonOutcomeUpdate(BaseModel):
    """Schema for updating learning outcomes."""
    outcome_id: str
    completed: bool


class LessonListResponse(BaseModel):
    """Schema for paginated lesson list response."""
    items: List[LessonWithAudioResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
