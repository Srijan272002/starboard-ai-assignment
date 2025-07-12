from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import Property, StandardizedProperty

logger = get_logger(__name__)
router = APIRouter()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class PropertyResponse(BaseModel):
    id: str
    address: str
    city: str
    state: str
    zipCode: str
    price: float
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    squareFeet: Optional[float] = None
    propertyType: str
    yearBuilt: Optional[int] = None
    imageUrl: Optional[str] = None
    county: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: str = ""
    
    class Config:
        from_attributes = True

class PropertySearchResponse(BaseModel):
    properties: List[PropertyResponse]
    total: int
    page: int
    limit: int

@router.get("/", response_model=PropertySearchResponse)
async def list_properties(
    county: Optional[str] = Query(None, description="Filter by county (cook, dallas, la)"),
    property_type: Optional[str] = Query(None, description="Filter by property type"),
    address: Optional[str] = Query(None, description="Search by address, city, or ZIP"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    min_sqft: Optional[float] = Query(None, description="Minimum square footage"),
    max_sqft: Optional[float] = Query(None, description="Maximum square footage"),
    page: int = Query(1, description="Page number", ge=1),
    limit: int = Query(20, description="Items per page", ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List properties with filtering options."""
    logger.info("Properties list requested", 
                county=county, 
                property_type=property_type, 
                page=page, 
                limit=limit)
    
    # Query the database for properties
    query = db.query(StandardizedProperty)
    
    # Apply filters
    if county:
        query = query.filter(StandardizedProperty.county == county)
    
    if property_type:
        query = query.filter(StandardizedProperty.property_type.ilike(f"%{property_type}%"))
    
    if address:
        address_filter = f"%{address}%"
        query = query.filter(
            (StandardizedProperty.address.ilike(address_filter)) |
            (StandardizedProperty.city.ilike(address_filter)) |
            (StandardizedProperty.zip_code.ilike(address_filter))
        )
    
    if min_price:
        query = query.filter(StandardizedProperty.price >= min_price)
    
    if max_price:
        query = query.filter(StandardizedProperty.price <= max_price)
    
    if min_sqft:
        query = query.filter(StandardizedProperty.square_feet >= min_sqft)
    
    if max_sqft:
        query = query.filter(StandardizedProperty.square_feet <= max_sqft)
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    
    # Execute query
    properties = query.all()
    
    # Convert to response format
    property_responses = []
    for prop in properties:
        property_responses.append(PropertyResponse(
            id=str(prop.id),
            address=prop.address,
            city=prop.city,
            state=prop.state,
            zipCode=prop.zip_code,
            price=prop.price,
            bedrooms=prop.bedrooms,
            bathrooms=prop.bathrooms,
            squareFeet=prop.square_feet,
            propertyType=prop.property_type,
            yearBuilt=prop.year_built,
            imageUrl=prop.image_url,
            county=prop.county,
            latitude=prop.latitude,
            longitude=prop.longitude,
            description=prop.description or ""
        ))
    
    return PropertySearchResponse(
        properties=property_responses,
        total=total,
        page=page,
        limit=limit
    )

@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(property_id: str, db: Session = Depends(get_db)):
    """Get property by ID."""
    logger.info("Property details requested", property_id=property_id)
    
    # Query the database for the property
    property = db.query(StandardizedProperty).filter(StandardizedProperty.id == property_id).first()
    
    if not property:
        logger.warning("Property not found", property_id=property_id)
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Convert to response format
    return PropertyResponse(
        id=str(property.id),
        address=property.address,
        city=property.city,
        state=property.state,
        zipCode=property.zip_code,
        price=property.price,
        bedrooms=property.bedrooms,
        bathrooms=property.bathrooms,
        squareFeet=property.square_feet,
        propertyType=property.property_type,
        yearBuilt=property.year_built,
        imageUrl=property.image_url,
        county=property.county,
        latitude=property.latitude,
        longitude=property.longitude,
        description=property.description or ""
    ) 