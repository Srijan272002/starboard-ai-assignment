from fastapi import APIRouter, HTTPException, Query, Request, Response
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import hashlib
import json
from backend.utils.market_analysis import get_market_trends, get_price_distribution
from backend.utils.logger import setup_logger
from backend.utils.cache import Cache

router = APIRouter(tags=["market"])
logger = setup_logger("market_routes")
cache = Cache()

def generate_etag(data: Any) -> str:
    """Generate ETag for data"""
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_str.encode()).hexdigest()

@router.get("/updates")
async def get_market_updates(
    request: Request,
    response: Response,
    timeframe: str = Query("6M", description="Time frame (1M, 3M, 6M, 1Y, 2Y, 5Y)")
) -> Dict[str, Any]:
    """
    Get market updates with version control and caching
    """
    try:
        # Check if client has current version
        if_none_match = request.headers.get("if-none-match")
        
        # Try to get from cache first
        cache_key = f"market_updates:{timeframe}"
        cached_data = await cache.get(cache_key)
        
        if cached_data:
            etag = generate_etag(cached_data)
            response.headers["ETag"] = etag
            
            # Return 304 if client has current version
            if if_none_match == etag:
                return Response(status_code=304)
            
            return cached_data
        
        # Get fresh data
        end_date = datetime.now()
        start_date = end_date - {
            "1M": timedelta(days=30),
            "3M": timedelta(days=90),
            "6M": timedelta(days=180),
            "1Y": timedelta(days=365),
            "2Y": timedelta(days=730),
            "5Y": timedelta(days=1825)
        }.get(timeframe, timedelta(days=180))
        
        # Get market data
        trends = await get_market_trends(start_date, end_date)
        distribution = await get_price_distribution()
        
        # Combine data with version info
        data = {
            "trends": trends,
            "distribution": distribution,
            "timestamp": datetime.now().isoformat(),
            "version": generate_etag({"trends": trends, "distribution": distribution})
        }
        
        # Cache the data
        await cache.set(cache_key, data, ttl=timedelta(minutes=5))
        
        # Set ETag
        etag = generate_etag(data)
        response.headers["ETag"] = etag
        
        return data
        
    except Exception as e:
        logger.error(f"Failed to get market updates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get market updates: {str(e)}"
        )

@router.get("/trends")
async def get_trends(
    request: Request,
    response: Response,
    timeframe: str = Query("6M", description="Time frame (1M, 3M, 6M, 1Y, 2Y, 5Y)")
) -> Dict[str, Any]:
    """
    Get market trends data for the specified timeframe
    """
    try:
        # Check if client has current version
        if_none_match = request.headers.get("if-none-match")
        
        # Try to get from cache first
        cache_key = f"market_trends:{timeframe}"
        cached_data = await cache.get(cache_key)
        
        if cached_data:
            etag = generate_etag(cached_data)
            response.headers["ETag"] = etag
            
            # Return 304 if client has current version
            if if_none_match == etag:
                return Response(status_code=304)
            
            return cached_data
        
        # Get fresh data
        end_date = datetime.now()
        start_date = end_date - {
            "1M": timedelta(days=30),
            "3M": timedelta(days=90),
            "6M": timedelta(days=180),
            "1Y": timedelta(days=365),
            "2Y": timedelta(days=730),
            "5Y": timedelta(days=1825)
        }.get(timeframe, timedelta(days=180))
        
        data = await get_market_trends(start_date, end_date)
        
        # Add version info
        data = {
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "version": generate_etag(data)
        }
        
        # Cache the data
        await cache.set(cache_key, data, ttl=timedelta(minutes=5))
        
        # Set ETag
        etag = generate_etag(data)
        response.headers["ETag"] = etag
        
        return data
        
    except Exception as e:
        logger.error(f"Failed to get market trends: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get market trends: {str(e)}"
        ) 