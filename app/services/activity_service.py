"""Activity tracking service."""

import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity, ActivityType


class ActivityService:
    """Service for tracking user activities."""

    @staticmethod
    async def log_activity(
        db: AsyncSession,
        user_id: str,
        activity_type: ActivityType,
        title: str,
        description: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Activity:
        """Log a user activity."""
        activity = Activity(
            user_id=user_id,
            activity_type=activity_type,
            title=title,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            extra_data=json.dumps(metadata) if metadata else None,
        )
        db.add(activity)
        await db.flush()
        return activity

    @staticmethod
    async def log_document_uploaded(
        db: AsyncSession,
        user_id: str,
        document_id: str,
        document_title: str,
    ) -> Activity:
        """Log document upload activity."""
        return await ActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.DOCUMENT_UPLOADED,
            title=f"Uploaded document: {document_title}",
            entity_type="document",
            entity_id=document_id,
        )

    @staticmethod
    async def log_document_processed(
        db: AsyncSession,
        user_id: str,
        document_id: str,
        document_title: str,
    ) -> Activity:
        """Log document processed activity."""
        return await ActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.DOCUMENT_PROCESSED,
            title=f"Document processed: {document_title}",
            description="Document has been processed and lesson is ready",
            entity_type="document",
            entity_id=document_id,
        )

    @staticmethod
    async def log_document_deleted(
        db: AsyncSession,
        user_id: str,
        document_title: str,
    ) -> Activity:
        """Log document deletion activity."""
        return await ActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.DOCUMENT_DELETED,
            title=f"Deleted document: {document_title}",
        )

    @staticmethod
    async def log_lesson_started(
        db: AsyncSession,
        user_id: str,
        lesson_id: str,
        lesson_title: str,
    ) -> Activity:
        """Log lesson started activity."""
        return await ActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.LESSON_STARTED,
            title=f"Started lesson: {lesson_title}",
            entity_type="lesson",
            entity_id=lesson_id,
        )

    @staticmethod
    async def log_lesson_completed(
        db: AsyncSession,
        user_id: str,
        lesson_id: str,
        lesson_title: str,
    ) -> Activity:
        """Log lesson completion activity."""
        return await ActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.LESSON_COMPLETED,
            title=f"Completed lesson: {lesson_title}",
            entity_type="lesson",
            entity_id=lesson_id,
        )

    @staticmethod
    async def log_profile_updated(
        db: AsyncSession,
        user_id: str,
    ) -> Activity:
        """Log profile update activity."""
        return await ActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.PROFILE_UPDATED,
            title="Updated profile settings",
        )

    @staticmethod
    async def log_password_changed(
        db: AsyncSession,
        user_id: str,
    ) -> Activity:
        """Log password change activity."""
        return await ActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.PASSWORD_CHANGED,
            title="Changed password",
        )

    @staticmethod
    async def log_login(
        db: AsyncSession,
        user_id: str,
    ) -> Activity:
        """Log login activity."""
        return await ActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.LOGIN,
            title="Logged in",
        )

    @staticmethod
    async def log_processing_failed(
        db: AsyncSession,
        user_id: str,
        document_id: str,
        document_title: str,
        step: str,
        error_message: str,
    ) -> Activity:
        """Log processing failure activity."""
        return await ActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.PROCESSING_FAILED,
            title=f"Processing failed: {document_title}",
            description=f"Failed at step: {step}. Error: {error_message}",
            entity_type="document",
            entity_id=document_id,
        )
