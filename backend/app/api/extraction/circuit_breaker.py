"""
Circuit Breaker - Failure recovery and circuit breaker pattern implementation
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import structlog
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Number of failures before opening
    success_threshold: int = 3  # Number of successes in half-open to close
    timeout_seconds: int = 60   # Time to wait before moving to half-open
    monitoring_window_seconds: int = 300  # Window for failure rate calculation
    failure_rate_threshold: float = 0.5  # Failure rate threshold (0.0-1.0)
    minimum_request_threshold: int = 10  # Minimum requests before considering failure rate
    reset_timeout_multiplier: float = 1.5  # Multiplier for timeout after each failure


class CircuitBreakerEvent(BaseModel):
    """Event in circuit breaker lifecycle"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str  # "request", "success", "failure", "state_change"
    state: CircuitBreakerState
    details: Dict[str, Any] = Field(default_factory=dict)


class CircuitBreakerMetrics(BaseModel):
    """Metrics for circuit breaker"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    state_changes: int = 0
    current_failure_streak: int = 0
    current_success_streak: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    total_time_open: float = 0.0  # Total time in open state (seconds)
    average_response_time: float = 0.0


class CircuitBreaker:
    """Circuit breaker implementation for external service calls"""
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        self.events: List[CircuitBreakerEvent] = []
        
        # State management
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state_change_time = datetime.utcnow()
        self.consecutive_timeout_failures = 0
        
        # Request tracking for failure rate calculation
        self.request_history: List[Dict[str, Any]] = []
        
        logger.info("Circuit breaker initialized", 
                   name=name,
                   state=self.state.value,
                   failure_threshold=self.config.failure_threshold)
    
    async def can_execute(self) -> bool:
        """
        Check if requests can be executed
        
        Returns:
            True if request can proceed, False if circuit is open
        """
        current_time = datetime.utcnow()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        elif self.state == CircuitBreakerState.OPEN:
            # Check if timeout has elapsed
            time_since_open = (current_time - self.state_change_time).total_seconds()
            timeout = self._calculate_timeout()
            
            if time_since_open >= timeout:
                # Move to half-open state
                await self._change_state(CircuitBreakerState.HALF_OPEN)
                return True
            
            # Still in open state, reject request
            self.metrics.rejected_requests += 1
            logger.debug("Circuit breaker rejecting request", 
                        name=self.name,
                        state=self.state.value,
                        time_since_open=time_since_open,
                        timeout=timeout)
            return False
        
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Allow limited requests to test service
            return True
        
        return False
    
    async def on_request(self):
        """Record that a request is being made"""
        self.metrics.total_requests += 1
        
        # Record request in history
        request_record = {
            "timestamp": datetime.utcnow(),
            "success": None  # Will be updated in on_success/on_failure
        }
        self.request_history.append(request_record)
        
        # Clean old history
        self._clean_request_history()
        
        await self._record_event("request", {"total_requests": self.metrics.total_requests})
    
    async def on_success(self):
        """Record a successful request"""
        self.metrics.successful_requests += 1
        self.metrics.last_success_time = datetime.utcnow()
        
        # Update request history
        if self.request_history:
            self.request_history[-1]["success"] = True
        
        if self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
            self.consecutive_timeout_failures = 0
        
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            
            # Check if we should close the circuit
            if self.success_count >= self.config.success_threshold:
                await self._change_state(CircuitBreakerState.CLOSED)
        
        # Update metrics
        self.metrics.current_success_streak += 1
        self.metrics.current_failure_streak = 0
        
        await self._record_event("success", {
            "success_count": self.success_count,
            "current_streak": self.metrics.current_success_streak
        })
        
        logger.debug("Circuit breaker recorded success", 
                    name=self.name,
                    state=self.state.value,
                    success_count=self.success_count)
    
    async def on_failure(self, error: Optional[Exception] = None):
        """Record a failed request"""
        self.metrics.failed_requests += 1
        self.metrics.last_failure_time = datetime.utcnow()
        self.failure_count += 1
        
        # Update request history
        if self.request_history:
            self.request_history[-1]["success"] = False
        
        # Check if it's a timeout error
        if error and self._is_timeout_error(error):
            self.consecutive_timeout_failures += 1
        else:
            self.consecutive_timeout_failures = 0
        
        # Update metrics
        self.metrics.current_failure_streak += 1
        self.metrics.current_success_streak = 0
        
        error_type = type(error).__name__ if error else "Unknown"
        await self._record_event("failure", {
            "failure_count": self.failure_count,
            "error_type": error_type,
            "current_streak": self.metrics.current_failure_streak
        })
        
        logger.warning("Circuit breaker recorded failure", 
                      name=self.name,
                      state=self.state.value,
                      failure_count=self.failure_count,
                      error_type=error_type)
        
        # Check state transitions
        if self.state == CircuitBreakerState.CLOSED:
            # Check if we should open the circuit
            if await self._should_open_circuit():
                await self._change_state(CircuitBreakerState.OPEN)
        
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Any failure in half-open state reopens the circuit
            await self._change_state(CircuitBreakerState.OPEN)
    
    async def _should_open_circuit(self) -> bool:
        """Determine if circuit should be opened"""
        # Check failure count threshold
        if self.failure_count >= self.config.failure_threshold:
            return True
        
        # Check failure rate if we have enough requests
        if len(self.request_history) >= self.config.minimum_request_threshold:
            failure_rate = self._calculate_failure_rate()
            if failure_rate >= self.config.failure_rate_threshold:
                return True
        
        # Check consecutive timeout failures (aggressive opening for timeouts)
        if self.consecutive_timeout_failures >= max(3, self.config.failure_threshold // 2):
            return True
        
        return False
    
    def _calculate_failure_rate(self) -> float:
        """Calculate current failure rate"""
        if not self.request_history:
            return 0.0
        
        recent_requests = [
            req for req in self.request_history
            if req["success"] is not None  # Only completed requests
        ]
        
        if not recent_requests:
            return 0.0
        
        failed_requests = sum(1 for req in recent_requests if not req["success"])
        return failed_requests / len(recent_requests)
    
    def _calculate_timeout(self) -> float:
        """Calculate timeout for open state"""
        base_timeout = self.config.timeout_seconds
        
        # Increase timeout based on consecutive failures
        multiplier = self.config.reset_timeout_multiplier ** max(0, self.failure_count - self.config.failure_threshold)
        
        # Cap the timeout to prevent extremely long waits
        max_timeout = base_timeout * 10
        return min(base_timeout * multiplier, max_timeout)
    
    def _is_timeout_error(self, error: Exception) -> bool:
        """Check if error is a timeout error"""
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()
        
        timeout_indicators = ['timeout', 'timedout', 'time out']
        
        return any(indicator in error_type or indicator in error_message 
                  for indicator in timeout_indicators)
    
    async def _change_state(self, new_state: CircuitBreakerState):
        """Change circuit breaker state"""
        old_state = self.state
        old_state_time = self.state_change_time
        
        self.state = new_state
        self.state_change_time = datetime.utcnow()
        self.metrics.state_changes += 1
        
        # Calculate time in previous state
        if old_state == CircuitBreakerState.OPEN:
            time_in_open = (self.state_change_time - old_state_time).total_seconds()
            self.metrics.total_time_open += time_in_open
        
        # Reset counters based on new state
        if new_state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
            self.consecutive_timeout_failures = 0
        
        elif new_state == CircuitBreakerState.OPEN:
            self.success_count = 0
        
        elif new_state == CircuitBreakerState.HALF_OPEN:
            self.success_count = 0
        
        await self._record_event("state_change", {
            "old_state": old_state.value,
            "new_state": new_state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count
        })
        
        logger.info("Circuit breaker state changed", 
                   name=self.name,
                   old_state=old_state.value,
                   new_state=new_state.value,
                   failure_count=self.failure_count)
    
    async def _record_event(self, event_type: str, details: Dict[str, Any]):
        """Record an event in circuit breaker history"""
        event = CircuitBreakerEvent(
            event_type=event_type,
            state=self.state,
            details=details
        )
        
        self.events.append(event)
        
        # Keep only recent events (last 1000)
        if len(self.events) > 1000:
            self.events = self.events[-1000:]
    
    def _clean_request_history(self):
        """Clean old requests from history"""
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.config.monitoring_window_seconds)
        
        self.request_history = [
            req for req in self.request_history
            if req["timestamp"] > cutoff_time
        ]
    
    async def force_open(self):
        """Manually force circuit breaker to open state"""
        await self._change_state(CircuitBreakerState.OPEN)
        logger.warning("Circuit breaker manually forced open", name=self.name)
    
    async def force_close(self):
        """Manually force circuit breaker to closed state"""
        await self._change_state(CircuitBreakerState.CLOSED)
        logger.info("Circuit breaker manually forced closed", name=self.name)
    
    async def force_half_open(self):
        """Manually force circuit breaker to half-open state"""
        await self._change_state(CircuitBreakerState.HALF_OPEN)
        logger.info("Circuit breaker manually forced half-open", name=self.name)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        current_time = datetime.utcnow()
        
        # Calculate time in current state
        time_in_current_state = (current_time - self.state_change_time).total_seconds()
        
        # Calculate current failure rate
        failure_rate = self._calculate_failure_rate()
        
        return {
            "name": self.name,
            "state": self.state.value,
            "time_in_current_state_seconds": time_in_current_state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_rate": failure_rate,
            "consecutive_timeout_failures": self.consecutive_timeout_failures,
            "next_timeout_seconds": self._calculate_timeout() if self.state == CircuitBreakerState.OPEN else None,
            "config": self.config.dict(),
            "metrics": self.metrics.dict(),
            "recent_requests": len(self.request_history)
        }
    
    def get_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent circuit breaker events"""
        return [event.dict() for event in self.events[-limit:]]
    
    async def reset(self):
        """Reset circuit breaker to initial state"""
        old_state = self.state
        
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.consecutive_timeout_failures = 0
        self.state_change_time = datetime.utcnow()
        self.request_history.clear()
        
        # Reset metrics but keep historical data
        self.metrics.current_failure_streak = 0
        self.metrics.current_success_streak = 0
        
        await self._record_event("reset", {"old_state": old_state.value})
        
        logger.info("Circuit breaker reset", name=self.name, old_state=old_state.value)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on circuit breaker"""
        status = self.get_status()
        
        # Determine health based on state and metrics
        if self.state == CircuitBreakerState.CLOSED:
            health_status = "healthy"
        elif self.state == CircuitBreakerState.HALF_OPEN:
            health_status = "recovering"
        else:  # OPEN
            health_status = "unhealthy"
        
        return {
            "status": health_status,
            "circuit_breaker": status,
            "recommendations": self._get_health_recommendations()
        }
    
    def _get_health_recommendations(self) -> List[str]:
        """Get health recommendations based on current state"""
        recommendations = []
        
        if self.state == CircuitBreakerState.OPEN:
            recommendations.append("Service is failing - circuit breaker is open")
            recommendations.append("Check service health and connectivity")
            
            if self.consecutive_timeout_failures > 0:
                recommendations.append("Multiple timeout failures detected - check network latency")
        
        elif self.state == CircuitBreakerState.HALF_OPEN:
            recommendations.append("Circuit breaker is testing service recovery")
            recommendations.append("Monitor for successful requests to close circuit")
        
        else:  # CLOSED
            failure_rate = self._calculate_failure_rate()
            if failure_rate > 0.2:  # 20% failure rate
                recommendations.append(f"High failure rate detected: {failure_rate:.1%}")
                recommendations.append("Monitor service stability")
            
            if self.failure_count > self.config.failure_threshold // 2:
                recommendations.append("Approaching failure threshold - monitor closely")
        
        return recommendations
    
    async def close(self):
        """Close circuit breaker and clean up resources"""
        logger.info("Closing circuit breaker", name=self.name)
        
        # Record final event
        await self._record_event("shutdown", {"final_state": self.state.value})
        
        # Clear history to free memory
        self.request_history.clear()
        self.events.clear() 