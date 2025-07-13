from fastapi import APIRouter, HTTPException, Query, Request, Response, Body
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import hashlib
import json
from backend.utils.logger import setup_logger
from backend.utils.cache import Cache
from backend.models.property import Property
from backend.utils.db import get_db_session
from sqlalchemy import select
from backend.agents.comparable_discovery import ComparableDiscoveryAgent
from backend.utils.validation import ValidatedProperty, PropertyMetrics, PropertyFinancials, PropertyType, Address, ZoningType

router = APIRouter(prefix="/api/properties", tags=["properties"])
logger = setup_logger("property_routes")
cache = Cache()

def generate_etag(data: Any) -> str:
    """Generate ETag for data"""
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_str.encode()).hexdigest()

@router.get("/updates")
async def get_property_updates(
    request: Request,
    response: Response,
    last_update: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
) -> Dict[str, Any]:
    """
    Get property updates with version control and caching
    """
    try:
        # Check if client has current version
        if_none_match = request.headers.get("if-none-match")
        
        # Try to get from cache first
        cache_key = f"property_updates:{last_update}:{limit}:{offset}"
        cached_data = await cache.get(cache_key)
        
        if cached_data:
            etag = generate_etag(cached_data)
            response.headers["ETag"] = etag
            
            # Return 304 if client has current version
            if if_none_match == etag:
                return Response(status_code=304)
            
            return cached_data
            
        # Get fresh data
        async with get_db_session() as session:
            query = select(Property)
            
            # Filter by last update if provided
            if last_update:
                try:
                    last_update_dt = datetime.fromisoformat(last_update)
                    query = query.where(Property.updated_at > last_update_dt)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid last_update format. Use ISO format."
                    )
            
            # Add pagination
            query = query.offset(offset).limit(limit)
            
            # Execute query
            result = await session.execute(query)
            properties = result.scalars().all()
            
            # Convert to dict and add metadata
            data = {
                "properties": [prop.to_dict() for prop in properties],
                "timestamp": datetime.now().isoformat(),
                "total": len(properties),
                "limit": limit,
                "offset": offset,
                "version": generate_etag(properties)
            }
            
            # Cache the data
            await cache.set(cache_key, data, ttl=timedelta(minutes=5))
            
            # Set ETag
            etag = generate_etag(data)
            response.headers["ETag"] = etag
            
            return data
            
    except Exception as e:
        logger.error(f"Failed to get property updates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get property updates: {str(e)}"
        )

@router.get("/{property_id}")
async def get_property(
    request: Request,
    response: Response,
    property_id: str
) -> Dict[str, Any]:
    """
    Get a specific property by ID
    """
    try:
        # Check if client has current version
        if_none_match = request.headers.get("if-none-match")
        
        # Try to get from cache first
        cache_key = f"property:{property_id}"
        cached_data = await cache.get(cache_key)
        
        if cached_data:
            etag = generate_etag(cached_data)
            response.headers["ETag"] = etag
            
            # Return 304 if client has current version
            if if_none_match == etag:
                return Response(status_code=304)
            
            return cached_data
            
        # Get fresh data
        async with get_db_session() as session:
            query = select(Property).where(Property.id == property_id)
            result = await session.execute(query)
            property = result.scalar_one_or_none()
            
            if not property:
                raise HTTPException(
                    status_code=404,
                    detail=f"Property {property_id} not found"
                )
            
            # Convert to dict and add metadata
            data = {
                "property": property.to_dict(),
                "timestamp": datetime.now().isoformat(),
                "version": generate_etag(property.to_dict())
            }
            
            # Cache the data
            await cache.set(cache_key, data, ttl=timedelta(minutes=5))
            
            # Set ETag
            etag = generate_etag(data)
            response.headers["ETag"] = etag
            
            return data
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get property {property_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get property: {str(e)}"
        ) 

@router.post("/comparables")
async def get_comparables(
    payload: dict = Body(...)
) -> dict:
    """
    Find comparable properties based on input property details.
    """
    try:
        address_str = payload.get("address")
        price = payload.get("price")
        square_footage = payload.get("square_footage")
        year_built_input = payload.get("year_built")
        current_year = datetime.datetime.now().year
        year_built = None
        try:
            year_built_val = int(year_built_input) if year_built_input else None
            if year_built_val is not None and 0 < year_built_val < 100:
                year_built = current_year - year_built_val
                logger.warning(f"Interpreted year_built={year_built_input} as {year_built} (years ago logic)")
            else:
                year_built = year_built_val
        except Exception:
            year_built = None
        property_type = payload.get("property_type")

        # Validate required fields
        if not all([address_str, price, square_footage, property_type]):
            raise HTTPException(status_code=400, detail="Missing required property fields.")

        # Parse address into components (simple split for now)
        # Assuming format: "street, city, state zipcode"
        try:
            street_part, rest = address_str.split(",", 1)
            city_part, state_zip = rest.strip().rsplit(",", 1)
            state, zip_code = state_zip.strip().split(" ", 1)
            address = Address(
                street=street_part.strip(),
                city=city_part.strip(),
                state=state.strip(),
                zip_code=zip_code.strip()
            )
        except ValueError:
            address = Address(
                street=address_str,
                city="Unknown",
                state="Unknown",
                zip_code="00000"
            )

        # Normalize and validate property_type
        property_type_str = str(property_type).strip().lower()
        property_type_map = {
            "industrial": PropertyType.INDUSTRIAL,
            "warehouse": PropertyType.WAREHOUSE,
            "manufacturing": PropertyType.MANUFACTURING,
            "flex": PropertyType.FLEX,
            "commercial": PropertyType.COMMERCIAL,
            "retail": PropertyType.RETAIL,
            "office": PropertyType.OFFICE,
            "mixed_use": PropertyType.MIXED_USE,
        }
        property_type_enum = property_type_map.get(property_type_str)
        if not property_type_enum:
            raise HTTPException(status_code=400, detail=f"Invalid property_type: {property_type_str}")

        # Use a valid zoning_type (default to M1 for industrial)
        zoning_type_enum = ZoningType.M1

        # Create a ValidatedProperty instance for the target property
        target_property = ValidatedProperty(
            id="temp_id",
            property_type=property_type_enum,
            zoning_type=zoning_type_enum,
            address=address,
            metrics=PropertyMetrics(
                total_square_feet=float(square_footage),
                year_built=year_built
            ),
            financials=PropertyFinancials(
                current_value=float(price),
                price_per_square_foot=float(price)/float(square_footage) if square_footage else None
            ),
            latitude=0.0,  # Default for now
            longitude=0.0,  # Default for now
            raw_data={}
        )

        # Fetch all properties from DB and convert to ValidatedProperty
        async with get_db_session() as session:
            result = await session.execute(select(Property))
            db_properties = result.scalars().all()
            
            # Convert DB properties to ValidatedProperty instances
            all_properties = []
            for prop in db_properties:
                try:
                    validated_prop = ValidatedProperty(
                        id=prop.id,
                        property_type=prop.property_type,
                        zoning_type=prop.zoning_type,
                        address=prop.address,
                        metrics=PropertyMetrics(
                            total_square_feet=prop.metrics.square_footage,
                            year_built=prop.metrics.year_built
                        ),
                        financials=PropertyFinancials(
                            current_value=prop.financials.price,
                            price_per_square_foot=prop.financials.price_per_square_foot
                        ),
                        latitude=prop.latitude,
                        longitude=prop.longitude,
                        raw_data=prop.raw_data or {}
                    )
                    all_properties.append(validated_prop)
                except Exception as e:
                    logger.warning(f"Failed to convert property {prop.id}: {str(e)}")
                    continue

        # Use ComparableDiscoveryAgent to find comparables
        agent = ComparableDiscoveryAgent()
        comparables = await agent.find_comparables(target_property, all_properties, limit=5)

        # Format response for frontend
        response = {
            "comparables": [
                {
                    "address": f"{c.property.address.street}, {c.property.address.city}, {c.property.address.state} {c.property.address.zip_code}",
                    "price": c.property.financials.current_value,
                    "square_footage": c.property.metrics.total_square_feet,
                    "similarity_score": c.similarity_score,
                    "confidence_score": c.confidence_score,
                }
                for c in comparables
            ]
        }
        return response
    except Exception as e:
        logger.error(f"Failed to fetch comparables: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch comparables: {str(e)}") 