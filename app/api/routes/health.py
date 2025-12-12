"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Check if the API is running."""
    return {"status": "healthy", "message": "Cognify API is running"}


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Cognify API",
        "version": "1.0.0",
        "description": "AI-powered learning content generation API",
    }
