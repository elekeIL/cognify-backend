"""Notification endpoints."""

import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func, update

from app.core.dependencies import DbSession, CurrentUser
from app.models.notification import Notification, NotificationType
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    MarkReadRequest,
    UnreadCountResponse,
)

router = APIRouter()


class MessageResponse(BaseModel):
    message: str


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
):
    """
    List user notifications with pagination.

    Supports filtering to show only unread notifications.
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    # Base query
    base_query = select(Notification).where(Notification.user_id == current_user.id)

    if unread_only:
        base_query = base_query.where(Notification.is_read == False)

    # Get total count
    count_query = select(func.count(Notification.id)).where(Notification.user_id == current_user.id)
    if unread_only:
        count_query = count_query.where(Notification.is_read == False)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get unread count
    unread_query = (
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id)
        .where(Notification.is_read == False)
    )
    unread_result = await db.execute(unread_query)
    unread_count = unread_result.scalar() or 0

    # Get paginated results
    query = (
        base_query
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    notifications = result.scalars().all()

    return NotificationListResponse(
        items=[
            NotificationResponse(
                id=n.id,
                type=n.type,
                title=n.title,
                description=n.description,
                entity_type=n.entity_type,
                entity_id=n.entity_id,
                action_url=n.action_url,
                is_read=n.is_read,
                created_at=n.created_at,
                read_at=n.read_at,
            )
            for n in notifications
        ],
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get the count of unread notifications.

    Useful for displaying badge count in header.
    """
    query = (
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id)
        .where(Notification.is_read == False)
    )

    result = await db.execute(query)
    unread_count = result.scalar() or 0

    return UnreadCountResponse(unread_count=unread_count)


@router.get("/recent", response_model=list[NotificationResponse])
async def get_recent_notifications(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 5,
):
    """
    Get recent notifications.

    Returns the most recent notifications for dropdown display.
    """
    if limit < 1 or limit > 20:
        limit = 5

    query = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    notifications = result.scalars().all()

    return [
        NotificationResponse(
            id=n.id,
            type=n.type,
            title=n.title,
            description=n.description,
            entity_type=n.entity_type,
            entity_id=n.entity_id,
            action_url=n.action_url,
            is_read=n.is_read,
            created_at=n.created_at,
            read_at=n.read_at,
        )
        for n in notifications
    ]


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get a specific notification by ID.
    """
    query = (
        select(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == current_user.id)
    )

    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        description=notification.description,
        entity_type=notification.entity_type,
        entity_id=notification.entity_id,
        action_url=notification.action_url,
        is_read=notification.is_read,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Mark a single notification as read.
    """
    query = (
        select(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == current_user.id)
    )

    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(notification)

    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        description=notification.description,
        entity_type=notification.entity_type,
        entity_id=notification.entity_id,
        action_url=notification.action_url,
        is_read=notification.is_read,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


@router.post("/mark-read", response_model=MessageResponse)
async def mark_notifications_read(
    request: MarkReadRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Mark multiple notifications as read.
    """
    stmt = (
        update(Notification)
        .where(Notification.id.in_(request.notification_ids))
        .where(Notification.user_id == current_user.id)
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )

    await db.execute(stmt)
    await db.flush()

    return MessageResponse(message=f"Marked {len(request.notification_ids)} notifications as read")


@router.post("/mark-all-read", response_model=MessageResponse)
async def mark_all_notifications_read(
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Mark all notifications as read.
    """
    stmt = (
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .where(Notification.is_read == False)
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )

    await db.execute(stmt)
    await db.flush()

    return MessageResponse(message="All notifications marked as read")


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Delete a notification.
    """
    query = (
        select(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == current_user.id)
    )

    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    await db.delete(notification)
    await db.flush()
