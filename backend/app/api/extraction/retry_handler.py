"""
Retry Handler - Intelligent retry logic with exponential backoff
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, TypeVar, Union
from enum import Enum
import structlog
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class RetryStrategy(str, Enum):
    """Retry strategies"""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIBONACCI_BACKOFF = "fibonacci_backoff"
    JITTERED_EXPONENTIAL = "jittered_exponential"


class RetryableException(str, Enum):
    """Types of exceptions that should trigger retries"""
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    SERVER_ERROR = "server_error"
    CONNECTION_ERROR = "connection_error"
    TEMPORARY_ERROR = "temporary_error"
    ALL = "all"


class RetryConfig(BaseModel):
    """Configuration for retry logic"""
    strategy: RetryStrategy = RetryStrategy.JITTERED_EXPONENTIAL
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0  # 5 minutes
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1  # 10% jitter
    retryable_exceptions: List[RetryableException] = Field(
        default_factory=lambda: [
            RetryableException.NETWORK_ERROR,
            RetryableException.TIMEOUT_ERROR,
            RetryableException.SERVER_ERROR,
            RetryableException.CONNECTION_ERROR,
            RetryableException.TEMPORARY_ERROR
        ]
    )
    retry_on_http_codes: List[int] = Field(
        default_factory=lambda: [429, 502, 503, 504, 408, 500]
    )
    stop_on_http_codes: List[int] = Field(
        default_factory=lambda: [401, 403, 404]
    )
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5


class RetryAttempt(BaseModel):
    """Information about a retry attempt"""
    attempt_number: int
    delay_seconds: float
    error_message: str
    error_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    http_status_code: Optional[int] = None


class RetryResult(BaseModel):
    """Result of retry operation"""
    success: bool
    result: Optional[Any] = None
    total_attempts: int = 0
    total_time_seconds: float = 0.0
    attempts: List[RetryAttempt] = Field(default_factory=list)
    final_error: Optional[str] = None
    final_error_type: Optional[str] = None


class RetryHandler:
    """Intelligent retry handler with multiple strategies"""
    
    def __init__(self, default_config: Optional[RetryConfig] = None):
        self.default_config = default_config or RetryConfig()
        self.retry_stats: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Retry handler initialized", 
                   strategy=self.default_config.strategy.value,
                   max_attempts=self.default_config.max_attempts)
    
    async def execute_with_retry(
        self,
        operation: Callable[..., T],
        operation_args: tuple = (),
        operation_kwargs: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> T:
        """
        Execute operation with retry logic
        
        Args:
            operation: Function to execute
            operation_args: Arguments for the operation
            operation_kwargs: Keyword arguments for the operation
            request_id: Optional request identifier for tracking
            custom_config: Custom retry configuration
            
        Returns:
            Result of the operation
            
        Raises:
            StarboardException: If all retry attempts fail
        """
        # Merge custom config with defaults
        config = self._merge_config(custom_config)
        operation_kwargs = operation_kwargs or {}
        
        start_time = datetime.utcnow()
        attempts = []
        
        logger.info("Starting retry operation", 
                   request_id=request_id,
                   max_attempts=config.max_attempts,
                   strategy=config.strategy.value)
        
        for attempt_num in range(1, config.max_attempts + 1):
            try:
                # Execute the operation
                if asyncio.iscoroutinefunction(operation):
                    result = await operation(*operation_args, **operation_kwargs)
                else:
                    result = operation(*operation_args, **operation_kwargs)
                
                # Success - update stats and return
                total_time = (datetime.utcnow() - start_time).total_seconds()
                
                if request_id:
                    self._update_retry_stats(request_id, True, attempt_num, total_time)
                
                logger.info("Operation succeeded", 
                           request_id=request_id,
                           attempt=attempt_num,
                           total_time=total_time)
                
                return result
                
            except Exception as e:
                error_type = type(e).__name__
                error_message = str(e)
                http_status_code = getattr(e, 'status_code', None)
                
                # Create retry attempt record
                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    delay_seconds=0.0,  # Will be set below
                    error_message=error_message,
                    error_type=error_type,
                    http_status_code=http_status_code
                )
                attempts.append(attempt)
                
                logger.warning("Operation failed", 
                              request_id=request_id,
                              attempt=attempt_num,
                              error=error_message,
                              error_type=error_type,
                              http_status_code=http_status_code)
                
                # Check if we should retry
                if not self._should_retry(e, config, attempt_num):
                    logger.info("Not retrying due to exception type or attempt limit", 
                               request_id=request_id,
                               error_type=error_type,
                               attempt=attempt_num)
                    break
                
                # Calculate delay for next attempt
                if attempt_num < config.max_attempts:
                    delay = self._calculate_delay(attempt_num, config)
                    attempt.delay_seconds = delay
                    
                    logger.info("Retrying after delay", 
                               request_id=request_id,
                               next_attempt=attempt_num + 1,
                               delay_seconds=delay)
                    
                    await asyncio.sleep(delay)
        
        # All attempts failed
        total_time = (datetime.utcnow() - start_time).total_seconds()
        final_attempt = attempts[-1] if attempts else None
        
        if request_id:
            self._update_retry_stats(request_id, False, len(attempts), total_time)
        
        logger.error("All retry attempts failed", 
                    request_id=request_id,
                    total_attempts=len(attempts),
                    total_time=total_time,
                    final_error=final_attempt.error_message if final_attempt else "Unknown")
        
        raise StarboardException(
            f"Operation failed after {len(attempts)} attempts. "
            f"Final error: {final_attempt.error_message if final_attempt else 'Unknown'}"
        )
    
    def _merge_config(self, custom_config: Optional[Dict[str, Any]]) -> RetryConfig:
        """Merge custom configuration with defaults"""
        if not custom_config:
            return self.default_config
        
        # Start with default config
        config_dict = self.default_config.dict()
        
        # Update with custom values
        config_dict.update(custom_config)
        
        return RetryConfig(**config_dict)
    
    def _should_retry(
        self,
        exception: Exception,
        config: RetryConfig,
        attempt_number: int
    ) -> bool:
        """Determine if we should retry based on exception and config"""
        # Check attempt limit
        if attempt_number >= config.max_attempts:
            return False
        
        # Check HTTP status codes
        http_status_code = getattr(exception, 'status_code', None)
        if http_status_code:
            if http_status_code in config.stop_on_http_codes:
                return False
            if http_status_code in config.retry_on_http_codes:
                return True
        
        # Check exception types
        exception_type = type(exception).__name__.lower()
        
        for retryable_type in config.retryable_exceptions:
            if retryable_type == RetryableException.ALL:
                return True
            
            if retryable_type == RetryableException.NETWORK_ERROR:
                if any(keyword in exception_type for keyword in 
                      ['network', 'connection', 'dns', 'socket']):
                    return True
            
            elif retryable_type == RetryableException.TIMEOUT_ERROR:
                if any(keyword in exception_type for keyword in 
                      ['timeout', 'timedout']):
                    return True
            
            elif retryable_type == RetryableException.RATE_LIMIT_ERROR:
                if any(keyword in exception_type for keyword in 
                      ['ratelimit', 'rate_limit', 'throttle']):
                    return True
                if http_status_code == 429:
                    return True
            
            elif retryable_type == RetryableException.SERVER_ERROR:
                if http_status_code and 500 <= http_status_code < 600:
                    return True
                if any(keyword in exception_type for keyword in 
                      ['server', 'internal', 'service']):
                    return True
            
            elif retryable_type == RetryableException.CONNECTION_ERROR:
                if any(keyword in exception_type for keyword in 
                      ['connection', 'connect', 'disconnect']):
                    return True
            
            elif retryable_type == RetryableException.TEMPORARY_ERROR:
                if any(keyword in exception_type for keyword in 
                      ['temporary', 'temp', 'transient']):
                    return True
        
        return False
    
    def _calculate_delay(self, attempt_number: int, config: RetryConfig) -> float:
        """Calculate delay for next attempt based on strategy"""
        if config.strategy == RetryStrategy.FIXED_DELAY:
            delay = config.initial_delay_seconds
        
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.initial_delay_seconds * attempt_number
        
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.initial_delay_seconds * (config.backoff_multiplier ** (attempt_number - 1))
        
        elif config.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            delay = config.initial_delay_seconds * self._fibonacci(attempt_number)
        
        elif config.strategy == RetryStrategy.JITTERED_EXPONENTIAL:
            base_delay = config.initial_delay_seconds * (config.backoff_multiplier ** (attempt_number - 1))
            jitter = base_delay * config.jitter_factor * random.uniform(-1, 1)
            delay = base_delay + jitter
        
        else:
            delay = config.initial_delay_seconds
        
        # Apply max delay limit
        delay = min(delay, config.max_delay_seconds)
        
        # Ensure minimum delay
        delay = max(delay, 0.1)
        
        return delay
    
    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number"""
        if n <= 1:
            return n
        elif n == 2:
            return 1
        
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b
    
    def _update_retry_stats(
        self,
        request_id: str,
        success: bool,
        attempts: int,
        total_time: float
    ):
        """Update retry statistics"""
        if request_id not in self.retry_stats:
            self.retry_stats[request_id] = {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "total_attempts": 0,
                "total_time": 0.0,
                "average_attempts": 0.0,
                "average_time": 0.0
            }
        
        stats = self.retry_stats[request_id]
        stats["total_executions"] += 1
        stats["total_attempts"] += attempts
        stats["total_time"] += total_time
        
        if success:
            stats["successful_executions"] += 1
        else:
            stats["failed_executions"] += 1
        
        # Update averages
        stats["average_attempts"] = stats["total_attempts"] / stats["total_executions"]
        stats["average_time"] = stats["total_time"] / stats["total_executions"]
    
    def get_retry_stats(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Get retry statistics"""
        if request_id:
            return self.retry_stats.get(request_id, {})
        return self.retry_stats.copy()
    
    def clear_retry_stats(self, request_id: Optional[str] = None):
        """Clear retry statistics"""
        if request_id:
            if request_id in self.retry_stats:
                del self.retry_stats[request_id]
        else:
            self.retry_stats.clear()
    
    async def test_retry_configuration(
        self,
        config: Optional[RetryConfig] = None
    ) -> Dict[str, Any]:
        """
        Test retry configuration with simulated failures
        
        Args:
            config: Retry configuration to test
            
        Returns:
            Test results
        """
        test_config = config or self.default_config
        
        async def failing_operation(fail_count: int):
            """Simulated operation that fails fail_count times"""
            if not hasattr(failing_operation, 'call_count'):
                failing_operation.call_count = 0
            
            failing_operation.call_count += 1
            
            if failing_operation.call_count <= fail_count:
                raise StarboardException(f"Simulated failure {failing_operation.call_count}")
            
            return f"Success after {failing_operation.call_count} attempts"
        
        test_results = {}
        
        # Test different failure scenarios
        for fail_count in [1, 2, test_config.max_attempts - 1, test_config.max_attempts]:
            # Reset call count
            if hasattr(failing_operation, 'call_count'):
                delattr(failing_operation, 'call_count')
            
            try:
                start_time = datetime.utcnow()
                result = await self.execute_with_retry(
                    operation=failing_operation,
                    operation_args=(fail_count,),
                    request_id=f"test_fail_{fail_count}",
                    custom_config=test_config.dict()
                )
                
                test_time = (datetime.utcnow() - start_time).total_seconds()
                test_results[f"fail_{fail_count}_times"] = {
                    "success": True,
                    "result": result,
                    "time_seconds": test_time
                }
                
            except Exception as e:
                test_time = (datetime.utcnow() - start_time).total_seconds()
                test_results[f"fail_{fail_count}_times"] = {
                    "success": False,
                    "error": str(e),
                    "time_seconds": test_time
                }
        
        return {
            "config": test_config.dict(),
            "test_results": test_results,
            "overall_stats": self.get_retry_stats()
        } 