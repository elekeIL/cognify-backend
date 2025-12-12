"""User settings endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import DbSession, CurrentUser
from app.schemas.settings import (
    ProfileSettingsUpdate,
    ProfileSettingsResponse,
    NotificationSettingsUpdate,
    NotificationSettingsResponse,
    LearningPreferencesUpdate,
    LearningPreferencesResponse,
    AllSettingsResponse,
)

router = APIRouter()


@router.get("/settings", response_model=AllSettingsResponse)
async def get_all_settings(
    current_user: CurrentUser,
):
    """
    Get all user settings.

    Returns profile, notification, and learning preference settings.
    """
    return AllSettingsResponse(
        profile=ProfileSettingsResponse(
            full_name=current_user.full_name,
            email=current_user.email,
            company=current_user.company,
            role=current_user.role,
            bio=current_user.bio,
            avatar_url=current_user.avatar_url,
            timezone=current_user.timezone,
            language=current_user.language,
        ),
        notifications=NotificationSettingsResponse(
            email_notifications=current_user.email_notifications,
            push_notifications=current_user.push_notifications,
            lesson_reminders=current_user.lesson_reminders,
            weekly_digest=current_user.weekly_digest,
            marketing_emails=current_user.marketing_emails,
        ),
        learning=LearningPreferencesResponse(
            daily_goal_minutes=current_user.daily_goal_minutes,
            preferred_lesson_length=current_user.preferred_lesson_length,
            auto_play_audio=current_user.auto_play_audio,
            playback_speed=current_user.playback_speed,
            theme=current_user.theme,
        ),
    )


@router.get("/settings/profile", response_model=ProfileSettingsResponse)
async def get_profile_settings(
    current_user: CurrentUser,
):
    """
    Get profile settings.
    """
    return ProfileSettingsResponse(
        full_name=current_user.full_name,
        email=current_user.email,
        company=current_user.company,
        role=current_user.role,
        bio=current_user.bio,
        avatar_url=current_user.avatar_url,
        timezone=current_user.timezone,
        language=current_user.language,
    )


@router.patch("/settings/profile", response_model=ProfileSettingsResponse)
async def update_profile_settings(
    settings: ProfileSettingsUpdate,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    Update profile settings.
    """
    if settings.full_name is not None:
        current_user.full_name = settings.full_name
    if settings.company is not None:
        current_user.company = settings.company
    if settings.role is not None:
        current_user.role = settings.role
    if settings.bio is not None:
        current_user.bio = settings.bio
    if settings.timezone is not None:
        current_user.timezone = settings.timezone
    if settings.language is not None:
        current_user.language = settings.language

    await db.flush()
    await db.refresh(current_user)

    return ProfileSettingsResponse(
        full_name=current_user.full_name,
        email=current_user.email,
        company=current_user.company,
        role=current_user.role,
        bio=current_user.bio,
        avatar_url=current_user.avatar_url,
        timezone=current_user.timezone,
        language=current_user.language,
    )


@router.get("/settings/notifications", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    current_user: CurrentUser,
):
    """
    Get notification settings.
    """
    return NotificationSettingsResponse(
        email_notifications=current_user.email_notifications,
        push_notifications=current_user.push_notifications,
        lesson_reminders=current_user.lesson_reminders,
        weekly_digest=current_user.weekly_digest,
        marketing_emails=current_user.marketing_emails,
    )


@router.patch("/settings/notifications", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    settings: NotificationSettingsUpdate,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    Update notification settings.
    """
    if settings.email_notifications is not None:
        current_user.email_notifications = settings.email_notifications
    if settings.push_notifications is not None:
        current_user.push_notifications = settings.push_notifications
    if settings.lesson_reminders is not None:
        current_user.lesson_reminders = settings.lesson_reminders
    if settings.weekly_digest is not None:
        current_user.weekly_digest = settings.weekly_digest
    if settings.marketing_emails is not None:
        current_user.marketing_emails = settings.marketing_emails

    await db.flush()
    await db.refresh(current_user)

    return NotificationSettingsResponse(
        email_notifications=current_user.email_notifications,
        push_notifications=current_user.push_notifications,
        lesson_reminders=current_user.lesson_reminders,
        weekly_digest=current_user.weekly_digest,
        marketing_emails=current_user.marketing_emails,
    )


@router.get("/settings/learning", response_model=LearningPreferencesResponse)
async def get_learning_preferences(
    current_user: CurrentUser,
):
    """
    Get learning preferences.
    """
    return LearningPreferencesResponse(
        daily_goal_minutes=current_user.daily_goal_minutes,
        preferred_lesson_length=current_user.preferred_lesson_length,
        auto_play_audio=current_user.auto_play_audio,
        playback_speed=current_user.playback_speed,
        theme=current_user.theme,
    )


@router.patch("/settings/learning", response_model=LearningPreferencesResponse)
async def update_learning_preferences(
    settings: LearningPreferencesUpdate,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    Update learning preferences.
    """
    if settings.daily_goal_minutes is not None:
        current_user.daily_goal_minutes = settings.daily_goal_minutes
    if settings.preferred_lesson_length is not None:
        current_user.preferred_lesson_length = settings.preferred_lesson_length
    if settings.auto_play_audio is not None:
        current_user.auto_play_audio = settings.auto_play_audio
    if settings.playback_speed is not None:
        current_user.playback_speed = settings.playback_speed
    if settings.theme is not None:
        current_user.theme = settings.theme

    await db.flush()
    await db.refresh(current_user)

    return LearningPreferencesResponse(
        daily_goal_minutes=current_user.daily_goal_minutes,
        preferred_lesson_length=current_user.preferred_lesson_length,
        auto_play_audio=current_user.auto_play_audio,
        playback_speed=current_user.playback_speed,
        theme=current_user.theme,
    )
