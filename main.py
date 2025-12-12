"""Main application entry point — Production Ready."""

import os
import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.db.session import init_db, close_db
from app.api.routes import api_router

# ─────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cognify")

settings = get_settings()


# ─────────────────────────────────────────────────────────────
# Global exception handler - logs full traceback
# ─────────────────────────────────────────────────────────────
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error("=" * 60)
        logger.error(f"500 ERROR on {request.method} {request.url.path}")
        logger.error(f"Exception: {type(exc).__name__}: {exc}")
        logger.error("Full traceback:")
        logger.error(traceback.format_exc())
        logger.error("=" * 60)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc)}
        )


# ─────────────────────────────────────────────────────────────
# Lifespan: Startup + Shutdown
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ─── Startup ───
    print(f"Starting up {settings.app_name} v{app.version}...")

    # Create required directories
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.audio_output_dir, exist_ok=True)

    # Initialize DB tables (only in dev — remove in prod if using Alembic)
    if settings.environment == "development":
        await init_db()
        print("Database tables ensured (dev mode)")

    print("Application startup complete")
    yield

    # ─── Shutdown ───
    print("Shutting down application...")
    await close_db()
    print("Database connections closed. Goodbye!")


# ─────────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    description="AI-powered learning content generation API for Cognify",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,  # Hide docs in prod
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
    # Remove default exception handlers in production
    default_response_class=JSONResponse,
)

# ─────────────────────────────────────────────────────────────
# Security & Performance Middleware
# ─────────────────────────────────────────────────────────────
app.add_middleware(BaseHTTPMiddleware, dispatch=catch_exceptions_middleware)

# Trusted hosts (prevent DNS rebinding, host header attacks)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts_list  # e.g. ["cognify.app", "api.cognify.app"]
)

# CORS — only allow your real frontend domains in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)

# ─────────────────────────────────────────────────────────────
# Static Files (audio output)
# ─────────────────────────────────────────────────────────────
app.mount(
    "/static/audio",
    StaticFiles(directory=settings.audio_output_dir, html=False),
    name="audio",
)

# ─────────────────────────────────────────────────────────────
# API Router
# ─────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1")


# ─────────────────────────────────────────────────────────────
# Health Check Endpoint
# ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name, "version": "1.0.0"}


# ─────────────────────────────────────────────────────────────
# Run with Uvicorn (only when running directly)
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug",
        workers=1 if settings.debug else None,  # Let uvicorn/gunicorn manage workers in prod
    )