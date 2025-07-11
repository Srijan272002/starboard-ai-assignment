"""
API Health Monitor - Monitors API health and performance
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import structlog
from pydantic import BaseModel, Field
import httpx

from app.core.config import settings
from app.core.exceptions import StarboardException
from .authentication import AuthenticationHandler
from .rate_limiter import RateLimiter

logger = structlog.get_logger(__name__)


class HealthStatus(str, Enum):
    """API health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheckResult(BaseModel):
    """Result of a health check"""
    api_name: str
    endpoint: str
    status: HealthStatus
    response_time_ms: int
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class APIHealthMetrics(BaseModel):
    """Health metrics for an API"""
    api_name: str
    current_status: HealthStatus = HealthStatus.UNKNOWN
    uptime_percentage: float = 0.0
    average_response_time: float = 0.0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_check: Optional[datetime] = None
    last_successful_check: Optional[datetime] = None
    consecutive_failures: int = 0
    recent_checks: List[HealthCheckResult] = Field(default_factory=list)


class APIHealthMonitor:
    """Monitors API health and performance"""
    
    def __init__(self):
        self.auth_handler = AuthenticationHandler()
        self.rate_limiter = RateLimiter()
        self.metrics: Dict[str, APIHealthMetrics] = {}
        self.monitoring_active = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.client = httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT,
            limits=httpx.Limits(max_connections=settings.MAX_CONCURRENT_REQUESTS)
        )
    
    async def add_api_for_monitoring(
        self,
        api_name: str,
        health_endpoint: str,
        county: Optional[str] = None,
        check_interval: int = 300
    ):
        """
        Add an API to health monitoring
        
        Args:
            api_name: Name of the API
            health_endpoint: Endpoint to check for health
            county: County name for authentication
            check_interval: Check interval in seconds
        """
        if api_name not in self.metrics:
            self.metrics[api_name] = APIHealthMetrics(api_name=api_name)
        
        # Configure authentication and rate limiting
        auth_config = self.auth_handler.get_county_auth_config(county or "default")
        self.rate_limiter.configure_rate_limit(api_name, county=county)
        
        # Store configuration
        self.metrics[api_name].metadata = {
            "health_endpoint": health_endpoint,
            "county": county,
            "check_interval": check_interval,
            "auth_config": auth_config.dict()
        }
        
        logger.info("API added to health monitoring", 
                   api_name=api_name,
                   health_endpoint=health_endpoint,
                   check_interval=check_interval)
    
    async def perform_health_check(
        self,
        api_name: str,
        endpoint: Optional[str] = None
    ) -> HealthCheckResult:
        """
        Perform a health check on an API
        
        Args:
            api_name: Name of the API
            endpoint: Specific endpoint to check (optional)
            
        Returns:
            HealthCheckResult
        """
        if api_name not in self.metrics:
            raise StarboardException(f"API {api_name} not configured for monitoring")
        
        metrics = self.metrics[api_name]
        check_endpoint = endpoint or metrics.metadata.get("health_endpoint")
        
        if not check_endpoint:
            raise StarboardException(f"No health endpoint configured for {api_name}")
        
        start_time = datetime.utcnow()
        
        try:
            # Wait for rate limit if needed
            await self.rate_limiter.wait_if_needed(api_name)
            
            # Get authentication headers
            auth_config = metrics.metadata.get("auth_config", {})
            county = metrics.metadata.get("county")
            
            if auth_config:
                from .authentication import AuthConfig, AuthType
                auth_config_obj = AuthConfig(**auth_config)
                headers = await self.auth_handler.get_auth_headers(auth_config_obj, county)
                params = await self.auth_handler.get_auth_params(auth_config_obj, county)
            else:
                headers = {}
                params = {}
            
            # Make the request
            response = await self.client.get(
                check_endpoint,
                headers=headers,
                params=params
            )
            
            # Calculate response time
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Record the request for rate limiting
            await self.rate_limiter.record_request(
                api_name,
                response.status_code,
                dict(response.headers)
            )
            
            # Determine health status
            if response.status_code == 200:
                status = HealthStatus.HEALTHY
            elif response.status_code in [201, 202, 204]:
                status = HealthStatus.HEALTHY
            elif response.status_code in [429, 503]:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            result = HealthCheckResult(
                api_name=api_name,
                endpoint=check_endpoint,
                status=status,
                response_time_ms=int(response_time),
                status_code=response.status_code,
                metadata={
                    "response_headers": dict(response.headers),
                    "response_size": len(response.content)
                }
            )
            
            logger.debug("Health check completed", 
                        api_name=api_name,
                        status=status.value,
                        response_time=response_time)
            
            return result
            
        except httpx.TimeoutException:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = HealthCheckResult(
                api_name=api_name,
                endpoint=check_endpoint,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=int(response_time),
                error_message="Request timeout"
            )
            
        except httpx.ConnectError:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = HealthCheckResult(
                api_name=api_name,
                endpoint=check_endpoint,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=int(response_time),
                error_message="Connection error"
            )
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = HealthCheckResult(
                api_name=api_name,
                endpoint=check_endpoint,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=int(response_time),
                error_message=str(e)
            )
        
        # Update metrics
        await self._update_metrics(result)
        
        logger.info("Health check completed", 
                   api_name=api_name,
                   status=result.status.value,
                   response_time=result.response_time_ms,
                   error=result.error_message)
        
        return result
    
    async def _update_metrics(self, result: HealthCheckResult):
        """Update health metrics based on check result"""
        metrics = self.metrics[result.api_name]
        
        # Update basic counters
        metrics.total_requests += 1
        if result.status == HealthStatus.HEALTHY:
            metrics.successful_requests += 1
            metrics.consecutive_failures = 0
            metrics.last_successful_check = result.timestamp
        else:
            metrics.failed_requests += 1
            metrics.consecutive_failures += 1
        
        # Update current status
        metrics.current_status = result.status
        metrics.last_check = result.timestamp
        
        # Calculate average response time
        metrics.average_response_time = (
            (metrics.average_response_time * (metrics.total_requests - 1) + result.response_time_ms)
            / metrics.total_requests
        )
        
        # Calculate uptime percentage
        if metrics.total_requests > 0:
            metrics.uptime_percentage = (metrics.successful_requests / metrics.total_requests) * 100
        
        # Store recent checks (keep last 100)
        metrics.recent_checks.append(result)
        if len(metrics.recent_checks) > 100:
            metrics.recent_checks = metrics.recent_checks[-100:]
    
    async def start_monitoring(self):
        """Start continuous health monitoring"""
        if self.monitoring_active:
            logger.warning("Health monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self):
        """Stop continuous health monitoring"""
        self.monitoring_active = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Check all registered APIs
                tasks = []
                for api_name in self.metrics.keys():
                    task = asyncio.create_task(self.perform_health_check(api_name))
                    tasks.append(task)
                
                if tasks:
                    # Wait for all health checks to complete
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Wait for the next check interval
                await asyncio.sleep(settings.API_HEALTH_CHECK_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in monitoring loop", error=str(e))
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    def get_api_health_status(self, api_name: str) -> Dict[str, Any]:
        """Get current health status for an API"""
        if api_name not in self.metrics:
            return {"status": "not_monitored"}
        
        metrics = self.metrics[api_name]
        
        # Calculate trend
        recent_statuses = [check.status for check in metrics.recent_checks[-10:]]
        healthy_count = sum(1 for status in recent_statuses if status == HealthStatus.HEALTHY)
        trend = "improving" if healthy_count > len(recent_statuses) / 2 else "degrading"
        
        return {
            "api_name": api_name,
            "current_status": metrics.current_status.value,
            "uptime_percentage": round(metrics.uptime_percentage, 2),
            "average_response_time": round(metrics.average_response_time, 2),
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "consecutive_failures": metrics.consecutive_failures,
            "last_check": metrics.last_check.isoformat() if metrics.last_check else None,
            "last_successful_check": metrics.last_successful_check.isoformat() if metrics.last_successful_check else None,
            "trend": trend,
            "monitoring_active": self.monitoring_active
        }
    
    def get_all_health_status(self) -> Dict[str, Any]:
        """Get health status for all monitored APIs"""
        overall_status = HealthStatus.HEALTHY
        api_statuses = {}
        
        for api_name in self.metrics.keys():
            api_status = self.get_api_health_status(api_name)
            api_statuses[api_name] = api_status
            
            # Determine overall status
            current_status = self.metrics[api_name].current_status
            if current_status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif current_status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED
        
        return {
            "overall_status": overall_status.value,
            "monitored_apis": len(self.metrics),
            "monitoring_active": self.monitoring_active,
            "apis": api_statuses,
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def get_health_history(
        self,
        api_name: str,
        hours: int = 24
    ) -> List[HealthCheckResult]:
        """Get health check history for an API"""
        if api_name not in self.metrics:
            return []
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        metrics = self.metrics[api_name]
        
        return [
            check for check in metrics.recent_checks
            if check.timestamp >= cutoff_time
        ]
    
    async def run_comprehensive_health_check(self) -> Dict[str, Any]:
        """Run a comprehensive health check on all monitored APIs"""
        logger.info("Running comprehensive health check")
        
        results = {}
        tasks = []
        
        for api_name in self.metrics.keys():
            task = asyncio.create_task(self.perform_health_check(api_name))
            tasks.append((api_name, task))
        
        for api_name, task in tasks:
            try:
                result = await task
                results[api_name] = {
                    "status": result.status.value,
                    "response_time_ms": result.response_time_ms,
                    "status_code": result.status_code,
                    "error_message": result.error_message,
                    "timestamp": result.timestamp.isoformat()
                }
            except Exception as e:
                results[api_name] = {
                    "status": "error",
                    "error_message": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        # Calculate summary
        total_apis = len(results)
        healthy_apis = sum(1 for r in results.values() if r["status"] == "healthy")
        degraded_apis = sum(1 for r in results.values() if r["status"] == "degraded")
        unhealthy_apis = total_apis - healthy_apis - degraded_apis
        
        summary = {
            "total_apis": total_apis,
            "healthy_apis": healthy_apis,
            "degraded_apis": degraded_apis,
            "unhealthy_apis": unhealthy_apis,
            "health_percentage": (healthy_apis / total_apis * 100) if total_apis > 0 else 0,
            "check_timestamp": datetime.utcnow().isoformat(),
            "results": results
        }
        
        logger.info("Comprehensive health check completed",
                   total_apis=total_apis,
                   healthy_apis=healthy_apis,
                   health_percentage=summary["health_percentage"])
        
        return summary
    
    async def close(self):
        """Close the health monitor"""
        await self.stop_monitoring()
        await self.client.aclose()
        logger.info("Health monitor closed") 