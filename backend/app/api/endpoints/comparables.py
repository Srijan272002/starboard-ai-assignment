from fastapi import APIRouter
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.get("/{property_id}")
async def get_comparables(property_id: str):
    """Get comparable properties for a given property."""
    logger.info("Comparables requested", property_id=property_id)
    # TODO: Implement comparable discovery algorithm (Phase 4)
    return {"message": f"Comparables for {property_id} - to be implemented in Phase 4"} 