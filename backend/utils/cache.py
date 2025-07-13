import json
import functools
from typing import Any, Optional, Callable
from redis import asyncio as aioredis
from datetime import timedelta
from backend.config.settings import get_settings
from backend.utils.logger import setup_logger

logger = setup_logger("cache")
settings = get_settings()

def cache_result(ttl: int = 300):
    """
    Decorator to cache function results
    
    Args:
        ttl: Time to live in seconds (default 5 minutes)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            try:
                # Try to get from cache first
                cached_value = await cache.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_value

                # If not in cache, execute function
                result = await func(*args, **kwargs)
                
                # Store in cache
                await cache.set(
                    cache_key,
                    result,
                    ttl=timedelta(seconds=ttl)
                )
                logger.debug(f"Cached result for {cache_key}")
                
                return result
            except Exception as e:
                logger.error(f"Cache decorator error for {cache_key}: {str(e)}")
                # On cache error, just execute the function
                return await func(*args, **kwargs)
                
        return wrapper
    return decorator

class Cache:
    def __init__(self):
        self.redis = None
        self.default_ttl = timedelta(minutes=30)

    async def connect(self):
        """
        Connect to Redis
        """
        if not self.redis:
            try:
                self.redis = await aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("Connected to Redis cache")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                raise

    async def disconnect(self):
        """
        Disconnect from Redis
        """
        if self.redis:
            await self.redis.close()
            self.redis = None
            logger.info("Disconnected from Redis cache")

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        """
        if not self.redis:
            await self.connect()
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None
    ) -> bool:
        """
        Set value in cache
        """
        if not self.redis:
            await self.connect()
        try:
            ttl = ttl or self.default_ttl
            return await self.redis.set(
                key,
                json.dumps(value),
                ex=int(ttl.total_seconds())
            )
        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete value from cache
        """
        if not self.redis:
            await self.connect()
        try:
            return bool(await self.redis.delete(key))
        except Exception as e:
            logger.error(f"Cache delete error: {str(e)}")
            return False

# Global cache instance
cache = Cache() 