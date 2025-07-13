"""
Main application module
"""

import logging
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from backend.config.settings import get_settings
from backend.utils.db import init_db
from backend.utils.scheduler import start_scheduler, stop_scheduler
from backend.routes import health, properties, market
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Starboard API",
    description="Real estate property management API",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag"]  # Expose ETag header for version control
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)  # Only compress responses larger than 1KB

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(properties.router, tags=["properties"])
app.include_router(market.router, prefix="/api/market", tags=["market"])

# Error handler for better debugging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception handler: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized successfully")

        # Start maintenance scheduler
        start_scheduler()
        logger.info("Maintenance scheduler started")
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        # Don't raise to allow app to start even with some initialization errors
        pass

@app.on_event("shutdown")
async def shutdown_event():
    try:
        # Stop maintenance scheduler
        stop_scheduler()
        logger.info("Maintenance scheduler stopped")
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}")
        pass 