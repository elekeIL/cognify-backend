"""User settings schemas for API validation."""

from typing import Optional

from pydantic import BaseModel, Field


class ProfileSettingsUpdate(BaseModel):
    """Schema for updating profile settings."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    timezone: Optional[str] = Field(None, max_length=100)
    language: Optional[str] = Field(None, max_length=10)


class NotificationSettingsUpdate(BaseModel):
    """Schema for updating notification settings."""
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    lesson_reminders: Optional[bool] = None
    weekly_digest: Optional[bool] = None
    marketing_emails: Optional[bool] = None


class LearningPreferencesUpdate(BaseModel):
    """Schema for updating learning preferences."""
    daily_goal_minutes: Optional[int] = Field(None, ge=5, le=240)
    preferred_lesson_length: Optional[str] = Field(None, pattern="^(short|medium|long)$")
    auto_play_audio: Optional[bool] = None
    playback_speed: Optional[float] = Field(None, ge=0.5, le=2.0)
    theme: Optional[str] = Field(None, pattern="^(light|dark|system)$")


class ProfileSettingsResponse(BaseModel):
    """Schema for profile settings response."""
    full_name: str
    email: str
    company: Optional[str] = None
    role: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: str
    language: str

    class Config:
        from_attributes = True


class NotificationSettingsResponse(BaseModel):
    """Schema for notification settings response."""
    email_notifications: bool
    push_notifications: bool
    lesson_reminders: bool
    weekly_digest: bool
    marketing_emails: bool

    class Config:
        from_attributes = True


class LearningPreferencesResponse(BaseModel):
    """Schema for learning preferences response."""
    daily_goal_minutes: int
    preferred_lesson_length: str
    auto_play_audio: bool
    playback_speed: float
    theme: str

    class Config:
        from_attributes = True


class AllSettingsResponse(BaseModel):
    """Schema for all user settings combined."""
    profile: ProfileSettingsResponse
    notifications: NotificationSettingsResponse
    learning: LearningPreferencesResponse
