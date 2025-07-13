from typing import Dict, List, Optional, Any
import aiohttp
import asyncio
from datetime import datetime, timedelta
import hashlib
import json
from backend.config.settings import get_settings
from backend.utils.logger import setup_logger
from backend.utils.cache import cache
from backend.utils.batch import batch_processor
from backend.utils.health import health_monitor

logger = setup_logger("attomdata_client")
settings = get_settings()

class RateLimiter:
    def __init__(self, rate_limit: int):
        self.rate_limit = rate_limit
        self.tokens = rate_limit
        self.last_update = datetime.now()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = datetime.now()
            time_passed = (now - self.last_update).total_seconds()
            self.tokens = min(
                self.rate_limit,
                self.tokens + time_passed * self.rate_limit
            )
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate_limit
                await asyncio.sleep(wait_time)
                self.tokens = 1
            
            self.tokens -= 1
            self.last_update = now

class AttomdataClient:
    def __init__(self):
        self.base_url = settings.ATTOMDATA_BASE_URL
        self.api_key = settings.ATTOMDATA_API_KEY
        self.rate_limiter = RateLimiter(settings.ATTOMDATA_RATE_LIMIT)
        self.session: Optional[aiohttp.ClientSession] = None
        self.retry_attempts = 3
        self.retry_delay = 1  # seconds
        
        # Register health check
        health_monitor.register_service(
            "attomdata_api",
            self.health_check,
            timeout=5.0
        )

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                "apikey": self.api_key,
                "accept": "application/json"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _generate_cache_key(self, method: str, endpoint: str, params: Dict) -> str:
        """
        Generate a unique cache key for the request
        """
        key_parts = [method, endpoint]
        if params:
            key_parts.append(json.dumps(params, sort_keys=True))
        key_string = ":".join(key_parts)
        return f"attomdata:{hashlib.md5(key_string.encode()).hexdigest()}"

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        use_cache: bool = True
    ) -> Dict:
        """
        Make a rate-limited request to the Attomdata API with retries and caching
        """
        if not self.session:
            raise RuntimeError("Client session not initialized")

        cache_key = self._generate_cache_key(method, endpoint, params)
        
        # Try to get from cache first
        if use_cache:
            cached_result = await cache.get(cache_key)
            if cached_result:
                logger.info(f"Cache hit for {endpoint}")
                return cached_result

        await self.rate_limiter.acquire()
        url = f"{self.base_url}/{endpoint}"

        for attempt in range(self.retry_attempts):
            try:
                async with self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    timeout=settings.ATTOMDATA_TIMEOUT
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    # Cache successful response
                    if use_cache:
                        await cache.set(
                            cache_key,
                            result,
                            ttl=timedelta(minutes=30)
                        )
                    
                    return result
                    
            except aiohttp.ClientError as e:
                logger.error(f"API request failed (attempt {attempt + 1}): {str(e)}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

    async def health_check(self) -> bool:
        """
        Check if the API is healthy
        """
        try:
            # Make a simple API call to check health
            await self._make_request(
                method="GET",
                endpoint="health",
                use_cache=False
            )
            return True
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    async def search_properties_batch(
        self,
        addresses: List[str],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search for multiple properties in batches
        """
        async def process_address(address: str) -> Dict[str, Any]:
            return await self.search_properties(address=address, **kwargs)

        return await batch_processor.process_batch(addresses, process_address)

    async def search_properties(
        self,
        address: Optional[str] = None,
        radius: Optional[float] = None,
        property_type: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Search for properties using various criteria
        """
        params = {
            "page": page,
            "pagesize": page_size
        }
        
        if address:
            params["address"] = address
        if radius:
            params["radius"] = radius
        if property_type:
            params["propertyType"] = property_type
        if min_size:
            params["minBuildingSize"] = min_size
        if max_size:
            params["maxBuildingSize"] = max_size

        return await self._make_request(
            method="GET",
            endpoint="property/detail",
            params=params
        )

    async def get_property_detail(
        self,
        property_id: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get detailed information for a specific property
        """
        return await self._make_request(
            method="GET",
            endpoint=f"property/detail/{property_id}",
            use_cache=use_cache
        )

    async def get_sales_history(
        self,
        property_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get sales history for a property
        """
        params = {}
        if start_date:
            params["startDate"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["endDate"] = end_date.strftime("%Y-%m-%d")

        return await self._make_request(
            method="GET",
            endpoint=f"property/detail/{property_id}/sales",
            params=params,
            use_cache=use_cache
        ) 