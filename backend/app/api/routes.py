"""
API Routes Configuration
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Dict, List, Optional, Any

from app.api.endpoints import (
    health, 
    api_discovery, 
    properties, 
    comparables, 
    extraction,
    data_storage,
    analysis
)
from app.api.counties.base import CountyAPI, PropertyData
from app.api.counties.cook_county import CookCountyAPI
from app.api.counties.dallas_county import DallasCountyAPI
from app.api.counties.la_county import LACountyAPI

# Create main router
router = APIRouter()

# Include endpoint routers
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(api_discovery.router, prefix="/discovery", tags=["discovery"])
router.include_router(properties.router, prefix="/properties", tags=["properties"])
router.include_router(comparables.router, prefix="/comparables", tags=["comparables"])
router.include_router(extraction.router, prefix="/extraction", tags=["extraction"])
router.include_router(data_storage.router, prefix="/storage", tags=["storage"])
router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])

# County API instances
_county_apis = {
    "cook": CookCountyAPI(),
    "dallas": DallasCountyAPI(),
    "la": LACountyAPI()
}

# Initialize county APIs
async def initialize_county_apis():
    """Initialize all county API connections"""
    for api in _county_apis.values():
        await api.initialize()

def _get_county_api(county: str) -> CountyAPI:
    """Get county API instance"""
    county = county.lower()
    if county not in _county_apis:
        raise HTTPException(status_code=404, detail=f"County '{county}' not supported")
    return _county_apis[county]


@router.get("/counties")
async def list_counties():
    """List all supported counties"""
    return {"counties": list(_county_apis.keys())}


@router.get("/properties/{county}/search")
async def search_properties(
    county: str,
    address: Optional[str] = None,
    city: Optional[str] = None,
    zip_code: Optional[str] = None,
    property_type: Optional[str] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, le=1000)
):
    """Search properties in specified county"""
    try:
        api = _get_county_api(county)
        
        # Build filters
        filters = {}
        if address:
            filters["address"] = address
        if city:
            filters["city"] = city
        if zip_code:
            filters["zip_code"] = zip_code
        if property_type:
            filters["property_type"] = property_type
        if min_area:
            filters["min_area"] = min_area
        if max_area:
            filters["max_area"] = max_area
        if min_value:
            filters["min_value"] = min_value
        if max_value:
            filters["max_value"] = max_value
            
        properties = await api.search_properties(filters, limit)
        
        # Format response to match frontend expectations
        return {
            "properties": properties,
            "total": len(properties),
            "page": page,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{county}/{property_id}", response_model=PropertyData)
async def get_property(county: str, property_id: str):
    """Get property data from specified county"""
    try:
        api = _get_county_api(county)
        property_data = await api.get_property(property_id)
        
        if not property_data:
            raise HTTPException(status_code=404, detail=f"Property {property_id} not found in {county} county")
            
        return property_data
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e)) 