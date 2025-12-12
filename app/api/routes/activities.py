"""Activity history endpoints."""

import math
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import select, func

from app.core.dependencies import DbSession, CurrentUser
from app.models.activity import Activity, ActivityType
from app.schemas.activity import ActivityResponse, ActivityListResponse

router = APIRouter()


@router.get("", response_model=ActivityListResponse)
async def list_activities(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
    activity_type: Optional[ActivityType] = None,
):
    """
    List user activities with pagination.

    Supports filtering by activity type.
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    # Base query
    base_query = select(Activity).where(Activity.user_id == current_user.id)

    if activity_type:
        base_query = base_query.where(Activity.activity_type == activity_type)

    # Get total count
    count_query = select(func.count(Activity.id)).where(Activity.user_id == current_user.id)
    if activity_type:
        count_query = count_query.where(Activity.activity_type == activity_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = (
        base_query
        .order_by(Activity.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    activities = result.scalars().all()

    return ActivityListResponse(
        items=[
            ActivityResponse(
                id=activity.id,
                activity_type=activity.activity_type,
                title=activity.title,
                description=activity.description,
                entity_type=activity.entity_type,
                entity_id=activity.entity_id,
                created_at=activity.created_at,
            )
            for activity in activities
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/recent", response_model=list[ActivityResponse])
async def get_recent_activities(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 10,
):
    """
    Get recent user activities.

    Returns the most recent activities without pagination.
    """
    if limit < 1 or limit > 50:
        limit = 10

    query = (
        select(Activity)
        .where(Activity.user_id == current_user.id)
        .order_by(Activity.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    activities = result.scalars().all()

    return [
        ActivityResponse(
            id=activity.id,
            activity_type=activity.activity_type,
            title=activity.title,
            description=activity.description,
            entity_type=activity.entity_type,
            entity_id=activity.entity_id,
            created_at=activity.created_at,
        )
        for activity in activities
    ]
