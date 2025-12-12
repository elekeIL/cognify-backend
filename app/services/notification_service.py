"""Notification service for creating user notifications."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType


class NotificationService:
    """Service for creating and managing notifications."""

    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: str,
        title: str,
        notification_type: NotificationType = NotificationType.INFO,
        description: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action_url: Optional[str] = None,
    ) -> Notification:
        """Create a new notification for a user."""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
        )
        db.add(notification)
        await db.flush()
        return notification

    @staticmethod
    async def notify_document_uploaded(
        db: AsyncSession,
        user_id: str,
        document_id: str,
        document_title: str,
    ) -> Notification:
        """Notify user that a document was uploaded."""
        return await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title="Document uploaded",
            description=f'"{document_title}" is being processed',
            notification_type=NotificationType.INFO,
            entity_type="document",
            entity_id=document_id,
            action_url=f"/documents/{document_id}",
        )

    @staticmethod
    async def notify_document_processed(
        db: AsyncSession,
        user_id: str,
        document_id: str,
        document_title: str,
        lesson_id: str,
    ) -> Notification:
        """Notify user that a document was successfully processed."""
        return await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title="Lesson completed",
            description=f'"{document_title}" is ready to review',
            notification_type=NotificationType.SUCCESS,
            entity_type="lesson",
            entity_id=lesson_id,
            action_url=f"/lessons/{lesson_id}",
        )

    @staticmethod
    async def notify_document_failed(
        db: AsyncSession,
        user_id: str,
        document_id: str,
        document_title: str,
        error_message: Optional[str] = None,
    ) -> Notification:
        """Notify user that document processing failed."""
        return await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title="Processing failed",
            description=f'Failed to process "{document_title}". {error_message or "Please try again."}',
            notification_type=NotificationType.ERROR,
            entity_type="document",
            entity_id=document_id,
            action_url=f"/documents/{document_id}",
        )

    @staticmethod
    async def notify_weekly_summary(
        db: AsyncSession,
        user_id: str,
        lessons_completed: int,
        total_time_minutes: int,
    ) -> Notification:
        """Send weekly learning summary notification."""
        return await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title="Weekly summary ready",
            description=f"You completed {lessons_completed} lessons and spent {total_time_minutes} minutes learning",
            notification_type=NotificationType.NEUTRAL,
            action_url="/dashboard",
        )

    @staticmethod
    async def notify_streak_milestone(
        db: AsyncSession,
        user_id: str,
        streak_days: int,
    ) -> Notification:
        """Notify user of a streak milestone."""
        return await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title=f"{streak_days}-day streak!",
            description=f"Congratulations! You've maintained a {streak_days}-day learning streak",
            notification_type=NotificationType.SUCCESS,
            action_url="/dashboard",
        )
