"""API routes package."""

from fastapi import APIRouter

from app.api.routes import (
    auth,
    documents,
    lessons,
    health,
    dashboard,
    activities,
    users,
    search,
    notifications,
    processing,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(processing.router, prefix="/documents", tags=["Document Processing"])
api_router.include_router(lessons.router, prefix="/lessons", tags=["Lessons"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(activities.router, prefix="/activities", tags=["Activities"])
api_router.include_router(users.router, prefix="/user", tags=["User Settings"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
