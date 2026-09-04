"""
PayPulse AI — FastAPI Application Entry Point
"""
import os
import sys

# Ensure root workspace directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("paypulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("PayPulse AI starting up...")
    try:
        await init_db()
        logger.info("Database initialized.")
    except Exception as e:
        logger.warning(f"DB init warning (may already exist): {e}")
    yield
    # Shutdown
    logger.info("PayPulse AI shutting down.")


app = FastAPI(
    title="PayPulse AI",
    description="AI-powered payment incident detection and investigation platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register routers
from backend.api import dashboard, incidents, audit, simulator  # noqa

app.include_router(dashboard.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(simulator.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "PayPulse AI API", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "paypulse-ai"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "Check server logs"}
    )
