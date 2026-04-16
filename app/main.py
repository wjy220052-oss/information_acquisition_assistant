"""
FastAPI application entry point

Provides the main API server with health check endpoint.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from app.api import recommendations_router, feedback_router, scheduler_router
from app.api.routes.home import router as home_router
from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import setup_logging, get_logger
from app.core.scheduler import start_scheduler, stop_scheduler
from app.repositories.recommendation_repository import RecommendationRepository

# Setup logging
logger = get_logger(__name__)

# Setup Jinja2 template engine (disable cache for test compatibility)
template_dir = Path(__file__).parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    cache_size=0,  # Disable cache to avoid test issues
    auto_reload=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan event handler

    Handles startup and shutdown events.

    Yields:
        None
    """
    settings = get_settings()

    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Start scheduler
    await start_scheduler()

    logger.info("Application startup complete")

    yield

    # Shutdown
    await stop_scheduler()
    logger.info("Application shutdown")


# Create FastAPI application
app = FastAPI(
    title=get_settings().APP_NAME,
    version=get_settings().APP_VERSION,
    description="面向个人用户的高质量中文内容推荐 Agent / 阅读决策助手",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Check if the application is running"
)
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint

    Returns:
        Dictionary with health status
    """
    settings = get_settings()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# Include routers
app.include_router(home_router)
app.include_router(
    recommendations_router,
    prefix="/api/recommendations",
    tags=["recommendations"]
)
app.include_router(
    feedback_router,
    prefix="/api/recommendations",
    tags=["feedback"]
)
app.include_router(
    scheduler_router,
    prefix="/api",
    tags=["scheduler"]
)
