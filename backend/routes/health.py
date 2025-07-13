from fastapi import APIRouter, HTTPException, Request, Response
from typing import Dict
import hashlib
import json
from datetime import timedelta
from backend.utils.health import health_monitor
from backend.utils.logger import setup_logger
from backend.utils.cache import Cache

router = APIRouter(prefix="/api/health", tags=["health"])
logger = setup_logger("health_routes")
cache = Cache()

def generate_etag(data: Dict) -> str:
    """Generate ETag for data"""
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_str.encode()).hexdigest()

@router.get("")
async def get_health(request: Request, response: Response) -> Dict:
    """
    Get health status of all services with version control and caching
    """
    try:
        # Check if client has current version
        if_none_match = request.headers.get("if-none-match")
        
        # Try to get from cache first
        cache_key = "health_status"
        cached_data = await cache.get(cache_key)
        
        if cached_data:
            etag = generate_etag(cached_data)
            response.headers["ETag"] = etag
            
            # Return 304 if client has current version
            if if_none_match == etag:
                return Response(status_code=304)
            
            return cached_data
            
        # Get fresh data
        health_data = await health_monitor.check_all()
        
        # Add version info
        data = {
            "status": health_data,
            "version": generate_etag(health_data)
        }
        
        # Cache the data
        await cache.set(cache_key, data, ttl=timedelta(seconds=30))  # Short cache for health checks
        
        # Set ETag
        etag = generate_etag(data)
        response.headers["ETag"] = etag
        
        return data
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Health check failed"
        ) 