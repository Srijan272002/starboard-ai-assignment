"""
Comparables Endpoints - API endpoints for property matching and comparison
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import PropertyComparable
from app.api.standardization.property_matcher import PropertyMatcher

logger = get_logger(__name__)
router = APIRouter()


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ComparableResponse(BaseModel):
    """Response model for comparable properties"""
    property_id: int
    comparable_property_id: int
    overall_similarity_score: float
    size_similarity: float
    location_similarity: float
    type_similarity: float
    age_similarity: float
    features_similarity: float
    distance_miles: float
    confidence_score: float

    class Config:
        from_attributes = True


class ComparablesResponse(BaseModel):
    """Response model for comparables endpoint"""
    success: bool
    message: str
    comparables: List[ComparableResponse]
    total_count: int


@router.get("/{property_id}", response_model=ComparablesResponse)
async def get_comparables(
    property_id: int,
    min_similarity: float = Query(0.5, ge=0.0, le=1.0),
    max_distance: float = Query(50.0, ge=0.0),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get comparable properties for a given property
    
    Args:
        property_id: ID of the reference property
        min_similarity: Minimum overall similarity score (0-1)
        max_distance: Maximum distance in miles
        limit: Maximum number of comparables to return
    """
    try:
        # Initialize property matcher
        matcher = PropertyMatcher(db)
        
        # Find comparables
        comparables = await matcher.find_comparables(
            property_id=property_id,
            min_similarity=min_similarity,
            max_distance=max_distance,
            limit=limit
        )
        
        return ComparablesResponse(
            success=True,
            message=f"Found {len(comparables)} comparable properties",
            comparables=[ComparableResponse.from_orm(comp) for comp in comparables],
            total_count=len(comparables)
        )
        
    except Exception as e:
        logger.error("Failed to get comparables", 
                    property_id=property_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get comparables: {str(e)}"
        ) 