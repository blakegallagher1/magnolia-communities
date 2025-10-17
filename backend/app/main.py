"""
GallagherMHP Command Platform - Main Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import make_asgi_app

from app.core.config import settings
from app.core.database import init_db
from app.api.v1.router import api_router
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown."""
    # Startup
    setup_logging()
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="GallagherMHP Command",
    description="AI-Assisted CRM + Deal Flow + Financial Screening + DD Suite for MHP Acquisition",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "gallagher-mhp-command"}


@app.get("/")
async def root():
    """Root endpoint with system information."""
    return {
        "service": "GallagherMHP Command Platform",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health",
        "metrics": "/metrics",
    }
