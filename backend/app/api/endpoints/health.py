from fastapi import APIRouter
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.get("/")
async def health_check():
    """Basic health check endpoint."""
    logger.info("Health check requested")
    return {"status": "healthy", "service": "Starboard AI Property Analysis"}

@router.get("/detailed")
async def detailed_health_check():
    """Detailed health check with system information."""
    logger.info("Detailed health check requested")
    
    # TODO: Add database connectivity check
    # TODO: Add external API connectivity checks
    
    return {
        "status": "healthy",
        "service": "Starboard AI Property Analysis",
        "version": "1.0.0",
        "components": {
            "database": "not_configured",
            "cook_county_api": "not_configured",
            "dallas_county_api": "not_configured",
            "la_county_api": "not_configured"
        }
    } 