"""
Main application entry point
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as api_router
from .core.config import settings
from .core.logging import setup_logging, get_logger
from .db.init_db import init_db

# Set up logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Starboard Property Analysis API",
    description="API for analyzing industrial properties across major US markets",
    version="1.0.0"
)

# Get CORS origins from settings
cors_origins = settings.get_cors_origins()
logger.info(f"Configuring CORS with allowed origins: {cors_origins}")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting application")
    try:
        # Initialize database
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error("Startup failed", error=str(e))
        # Continue startup even if database initialization fails
        # This allows the application to start in environments without a database

@app.get("/")
async def root():
    return {"message": "Starboard Property Analysis System"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    """Handle OPTIONS requests for CORS preflight"""
    logger.info(f"OPTIONS request received for path: /{full_path}")
    response = Response()
    origin = request.headers.get("origin", "")
    logger.info(f"Request origin: {origin}")
    
    # Log if origin is in allowed origins
    if origin in cors_origins:
        logger.info(f"Origin {origin} is allowed")
    else:
        logger.warning(f"Origin {origin} is not in allowed origins: {cors_origins}")
    
    return response 