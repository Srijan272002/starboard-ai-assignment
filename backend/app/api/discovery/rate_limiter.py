"""
Rate Limiter - Intelligent rate limiting system with auto-detection
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple
from enum import Enum
import structlog
from pydantic import BaseModel
import redis.asyncio as redis

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies"""
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    TOKEN_BUCKET = "token_bucket"
    ADAPTIVE = "adaptive"


class RateLimitConfig(BaseModel):
    """Rate limit configuration"""
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    backoff_factor: float = 1.5
    max_backoff: float = 300.0  # 5 minutes
    adaptive_enabled: bool = True
    
    # Auto-detection settings
    auto_detect_enabled: bool = True
    detection_window: int = 60  # seconds
    detection_threshold: float = 0.8  # Trigger detection at 80% of detected limit


class RateLimitState(BaseModel):
    """Current rate limit state"""
    requests_made: int = 0
    window_start: datetime
    last_request_time: Optional[datetime] = None
    current_backoff: float = 0.0
    detected_limit: Optional[int] = None
    is_rate_limited: bool = False
    consecutive_429s: int = 0


class RateLimiter:
    """Intelligent rate limiting system with auto-detection"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.local_state: Dict[str, RateLimitState] = {}
        self.configs: Dict[str, RateLimitConfig] = {}
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection if available"""
        try:
            if settings.RATE_LIMIT_REDIS_URL:
                self.redis_client = redis.from_url(
                    settings.RATE_LIMIT_REDIS_URL,
                    decode_responses=True
                )
                logger.info("Redis rate limiter initialized")
        except Exception as e:
            logger.warning("Redis not available, using local rate limiting", error=str(e))
    
    def configure_rate_limit(
        self,
        api_name: str,
        config: Optional[RateLimitConfig] = None,
        county: Optional[str] = None
    ) -> RateLimitConfig:
        """
        Configure rate limiting for an API
        
        Args:
            api_name: Name of the API
            config: Rate limit configuration
            county: County name for default settings
            
        Returns:
            Configured RateLimitConfig
        """
        if config is None:
            config = self._get_default_config(county)
        
        self.configs[api_name] = config
        
        # Initialize state if not exists
        if api_name not in self.local_state:
            self.local_state[api_name] = RateLimitState(
                window_start=datetime.utcnow()
            )
        
        logger.info("Rate limit configured", 
                   api_name=api_name,
                   strategy=config.strategy.value,
                   rpm=config.requests_per_minute)
        
        return config
    
    def _get_default_config(self, county: Optional[str] = None) -> RateLimitConfig:
        """Get default rate limit configuration for a county"""
        if county:
            county_lower = county.lower()
            
            if county_lower == "cook":
                return RateLimitConfig(
                    requests_per_minute=settings.COOK_COUNTY_RATE_LIMIT // 60,
                    requests_per_hour=settings.COOK_COUNTY_RATE_LIMIT,
                    burst_limit=20
                )
            elif county_lower == "dallas":
                return RateLimitConfig(
                    requests_per_minute=settings.DALLAS_COUNTY_RATE_LIMIT // 60,
                    requests_per_hour=settings.DALLAS_COUNTY_RATE_LIMIT,
                    burst_limit=10
                )
            elif county_lower == "la":
                return RateLimitConfig(
                    requests_per_minute=settings.LA_COUNTY_RATE_LIMIT // 60,
                    requests_per_hour=settings.LA_COUNTY_RATE_LIMIT,
                    burst_limit=30
                )
        
        return RateLimitConfig(
            requests_per_minute=settings.DEFAULT_RATE_LIMIT,
            requests_per_hour=settings.DEFAULT_RATE_LIMIT * 60
        )
    
    async def check_rate_limit(
        self,
        api_name: str,
        endpoint: Optional[str] = None
    ) -> Tuple[bool, float]:
        """
        Check if request is allowed under rate limiting
        
        Args:
            api_name: Name of the API
            endpoint: Specific endpoint (optional)
            
        Returns:
            Tuple of (is_allowed, wait_time_seconds)
        """
        key = f"{api_name}:{endpoint}" if endpoint else api_name
        
        # Get or create config
        if api_name not in self.configs:
            self.configure_rate_limit(api_name)
        
        config = self.configs[api_name]
        
        if self.redis_client:
            return await self._check_rate_limit_redis(key, config)
        else:
            return await self._check_rate_limit_local(key, config)
    
    async def _check_rate_limit_redis(
        self,
        key: str,
        config: RateLimitConfig
    ) -> Tuple[bool, float]:
        """Check rate limit using Redis"""
        try:
            current_time = time.time()
            
            if config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                return await self._sliding_window_redis(key, config, current_time)
            elif config.strategy == RateLimitStrategy.FIXED_WINDOW:
                return await self._fixed_window_redis(key, config, current_time)
            elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return await self._token_bucket_redis(key, config, current_time)
            else:
                return await self._adaptive_redis(key, config, current_time)
                
        except Exception as e:
            logger.error("Redis rate limit check failed", key=key, error=str(e))
            # Fallback to local rate limiting
            return await self._check_rate_limit_local(key, config)
    
    async def _check_rate_limit_local(
        self,
        key: str,
        config: RateLimitConfig
    ) -> Tuple[bool, float]:
        """Check rate limit using local state"""
        if key not in self.local_state:
            self.local_state[key] = RateLimitState(
                window_start=datetime.utcnow()
            )
        
        state = self.local_state[key]
        current_time = datetime.utcnow()
        
        if config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return self._sliding_window_local(state, config, current_time)
        elif config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return self._fixed_window_local(state, config, current_time)
        elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return self._token_bucket_local(state, config, current_time)
        else:
            return self._adaptive_local(state, config, current_time)
    
    async def _sliding_window_redis(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: float
    ) -> Tuple[bool, float]:
        """Sliding window rate limiting with Redis"""
        window_key = f"rate_limit:{key}:sliding"
        window_size = 60  # 1 minute window
        
        # Remove old entries
        await self.redis_client.zremrangebyscore(
            window_key,
            0,
            current_time - window_size
        )
        
        # Count current requests
        current_count = await self.redis_client.zcard(window_key)
        
        if current_count >= config.requests_per_minute:
            # Calculate wait time
            oldest_request = await self.redis_client.zrange(window_key, 0, 0, withscores=True)
            if oldest_request:
                wait_time = oldest_request[0][1] + window_size - current_time
                return False, max(wait_time, 0)
            return False, window_size
        
        # Add current request
        await self.redis_client.zadd(window_key, {str(current_time): current_time})
        await self.redis_client.expire(window_key, window_size)
        
        return True, 0.0
    
    def _sliding_window_local(
        self,
        state: RateLimitState,
        config: RateLimitConfig,
        current_time: datetime
    ) -> Tuple[bool, float]:
        """Sliding window rate limiting with local state"""
        window_size = timedelta(minutes=1)
        window_start = current_time - window_size
        
        # Reset if window is old
        if state.window_start < window_start:
            state.requests_made = 0
            state.window_start = window_start
        
        if state.requests_made >= config.requests_per_minute:
            wait_time = (state.window_start + window_size - current_time).total_seconds()
            return False, max(wait_time, 0)
        
        return True, 0.0
    
    async def _fixed_window_redis(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: float
    ) -> Tuple[bool, float]:
        """Fixed window rate limiting with Redis"""
        window_key = f"rate_limit:{key}:fixed"
        window_size = 60  # 1 minute window
        window_id = int(current_time // window_size)
        
        current_key = f"{window_key}:{window_id}"
        current_count = await self.redis_client.get(current_key) or 0
        current_count = int(current_count)
        
        if current_count >= config.requests_per_minute:
            next_window = (window_id + 1) * window_size
            wait_time = next_window - current_time
            return False, wait_time
        
        # Increment counter
        await self.redis_client.incr(current_key)
        await self.redis_client.expire(current_key, window_size)
        
        return True, 0.0
    
    def _fixed_window_local(
        self,
        state: RateLimitState,
        config: RateLimitConfig,
        current_time: datetime
    ) -> Tuple[bool, float]:
        """Fixed window rate limiting with local state"""
        window_size = timedelta(minutes=1)
        window_start = datetime(
            current_time.year,
            current_time.month,
            current_time.day,
            current_time.hour,
            current_time.minute
        )
        
        # Reset window if needed
        if state.window_start != window_start:
            state.requests_made = 0
            state.window_start = window_start
        
        if state.requests_made >= config.requests_per_minute:
            next_window = window_start + window_size
            wait_time = (next_window - current_time).total_seconds()
            return False, wait_time
        
        return True, 0.0
    
    async def _token_bucket_redis(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: float
    ) -> Tuple[bool, float]:
        """Token bucket rate limiting with Redis"""
        bucket_key = f"rate_limit:{key}:bucket"
        last_refill_key = f"rate_limit:{key}:last_refill"
        
        # Get current tokens and last refill time
        tokens = await self.redis_client.get(bucket_key) or config.burst_limit
        last_refill = await self.redis_client.get(last_refill_key) or current_time
        
        tokens = float(tokens)
        last_refill = float(last_refill)
        
        # Calculate tokens to add
        time_passed = current_time - last_refill
        tokens_to_add = time_passed * (config.requests_per_minute / 60.0)
        tokens = min(config.burst_limit, tokens + tokens_to_add)
        
        if tokens < 1:
            wait_time = (1 - tokens) / (config.requests_per_minute / 60.0)
            return False, wait_time
        
        # Consume token
        tokens -= 1
        
        # Update Redis
        await self.redis_client.set(bucket_key, tokens, ex=3600)
        await self.redis_client.set(last_refill_key, current_time, ex=3600)
        
        return True, 0.0
    
    def _token_bucket_local(
        self,
        state: RateLimitState,
        config: RateLimitConfig,
        current_time: datetime
    ) -> Tuple[bool, float]:
        """Token bucket rate limiting with local state"""
        if not hasattr(state, 'tokens'):
            state.tokens = config.burst_limit
        
        # Calculate tokens to add
        if state.last_request_time:
            time_passed = (current_time - state.last_request_time).total_seconds()
            tokens_to_add = time_passed * (config.requests_per_minute / 60.0)
            state.tokens = min(config.burst_limit, state.tokens + tokens_to_add)
        
        if state.tokens < 1:
            wait_time = (1 - state.tokens) / (config.requests_per_minute / 60.0)
            return False, wait_time
        
        return True, 0.0
    
    async def _adaptive_redis(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: float
    ) -> Tuple[bool, float]:
        """Adaptive rate limiting with Redis - adjusts based on 429 responses"""
        # Use sliding window as base, but adjust limits based on detected rate limits
        detected_limit_key = f"rate_limit:{key}:detected"
        detected_limit = await self.redis_client.get(detected_limit_key)
        
        if detected_limit:
            # Use detected limit with safety margin
            adaptive_config = config.copy()
            adaptive_config.requests_per_minute = int(float(detected_limit) * 0.8)
            return await self._sliding_window_redis(key, adaptive_config, current_time)
        
        return await self._sliding_window_redis(key, config, current_time)
    
    def _adaptive_local(
        self,
        state: RateLimitState,
        config: RateLimitConfig,
        current_time: datetime
    ) -> Tuple[bool, float]:
        """Adaptive rate limiting with local state"""
        if state.detected_limit:
            # Use detected limit with safety margin
            adaptive_config = config.copy()
            adaptive_config.requests_per_minute = int(state.detected_limit * 0.8)
            return self._sliding_window_local(state, adaptive_config, current_time)
        
        return self._sliding_window_local(state, config, current_time)
    
    async def record_request(
        self,
        api_name: str,
        endpoint: Optional[str] = None,
        status_code: int = 200,
        response_headers: Optional[Dict[str, str]] = None
    ):
        """
        Record a request and update rate limiting state
        
        Args:
            api_name: Name of the API
            endpoint: Specific endpoint (optional)
            status_code: HTTP status code
            response_headers: Response headers for rate limit detection
        """
        key = f"{api_name}:{endpoint}" if endpoint else api_name
        
        # Update local state
        if key in self.local_state:
            state = self.local_state[key]
            state.requests_made += 1
            state.last_request_time = datetime.utcnow()
            
            # Handle 429 responses
            if status_code == 429:
                state.consecutive_429s += 1
                state.is_rate_limited = True
                
                # Increase backoff
                config = self.configs.get(api_name, self._get_default_config())
                state.current_backoff = min(
                    state.current_backoff * config.backoff_factor,
                    config.max_backoff
                )
                
                logger.warning("Rate limit exceeded", api_name=api_name, 
                             consecutive_429s=state.consecutive_429s)
            else:
                state.consecutive_429s = 0
                state.is_rate_limited = False
                state.current_backoff = 0.0
        
        # Auto-detect rate limits from headers
        if response_headers and api_name in self.configs:
            await self._detect_rate_limits(api_name, response_headers)
    
    async def _detect_rate_limits(
        self,
        api_name: str,
        headers: Dict[str, str]
    ):
        """Auto-detect rate limits from response headers"""
        config = self.configs[api_name]
        if not config.auto_detect_enabled:
            return
        
        # Common rate limit headers
        rate_limit_headers = {
            "x-ratelimit-limit": "limit",
            "x-ratelimit-remaining": "remaining",
            "x-rate-limit-limit": "limit",
            "x-rate-limit-remaining": "remaining",
            "rate-limit-limit": "limit",
            "rate-limit-remaining": "remaining"
        }
        
        detected_info = {}
        for header, info_type in rate_limit_headers.items():
            if header in headers:
                try:
                    detected_info[info_type] = int(headers[header])
                except ValueError:
                    continue
        
        if "limit" in detected_info:
            state = self.local_state.get(api_name)
            if state:
                state.detected_limit = detected_info["limit"]
                
                # Update Redis if available
                if self.redis_client:
                    await self.redis_client.set(
                        f"rate_limit:{api_name}:detected",
                        detected_info["limit"],
                        ex=3600
                    )
                
                logger.info("Rate limit auto-detected", 
                           api_name=api_name,
                           detected_limit=detected_info["limit"])
    
    async def wait_if_needed(
        self,
        api_name: str,
        endpoint: Optional[str] = None
    ):
        """Wait if rate limiting requires it"""
        is_allowed, wait_time = await self.check_rate_limit(api_name, endpoint)
        
        if not is_allowed and wait_time > 0:
            logger.info("Rate limit wait required", 
                       api_name=api_name,
                       wait_time=wait_time)
            await asyncio.sleep(wait_time)
    
    async def get_rate_limit_status(self, api_name: str) -> Dict[str, Any]:
        """Get current rate limit status for an API"""
        state = self.local_state.get(api_name)
        config = self.configs.get(api_name)
        
        if not state or not config:
            return {"status": "not_configured"}
        
        return {
            "status": "rate_limited" if state.is_rate_limited else "active",
            "requests_made": state.requests_made,
            "current_backoff": state.current_backoff,
            "detected_limit": state.detected_limit,
            "configured_limit": config.requests_per_minute,
            "consecutive_429s": state.consecutive_429s,
            "window_start": state.window_start.isoformat() if state.window_start else None
        }
    
    async def close(self):
        """Close Redis connection if available"""
        if self.redis_client:
            await self.redis_client.close() 