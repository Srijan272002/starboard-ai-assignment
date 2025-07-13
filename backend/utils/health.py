from typing import Dict, List, Optional
import time
import asyncio
from datetime import datetime, timedelta
from backend.utils.logger import setup_logger
from backend.utils.cache import cache

logger = setup_logger("health")

class HealthMonitor:
    def __init__(self):
        self.services: Dict[str, Dict] = {}
        self.check_interval = 60  # seconds
        self._running = False
        self._last_check: Dict[str, datetime] = {}

    def register_service(
        self,
        name: str,
        check_fn: callable,
        timeout: float = 5.0,
        dependencies: Optional[List[str]] = None
    ):
        """
        Register a service for health monitoring
        """
        self.services[name] = {
            "check_fn": check_fn,
            "timeout": timeout,
            "dependencies": dependencies or [],
            "status": "unknown",
            "last_check": None,
            "error": None
        }
        logger.info(f"Registered service: {name}")

    async def check_service(self, name: str) -> bool:
        """
        Check health of a single service
        """
        service = self.services[name]
        try:
            # Check dependencies first
            for dep in service["dependencies"]:
                if not await self.check_service(dep):
                    raise Exception(f"Dependency {dep} is unhealthy")

            # Run the health check with timeout
            result = await asyncio.wait_for(
                service["check_fn"](),
                timeout=service["timeout"]
            )
            
            service["status"] = "healthy"
            service["last_check"] = datetime.now()
            service["error"] = None
            
            # Cache the health status
            await cache.set(
                f"health:{name}",
                {
                    "status": service["status"],
                    "last_check": service["last_check"].isoformat(),
                    "error": None
                },
                ttl=timedelta(minutes=5)
            )
            
            return True

        except Exception as e:
            service["status"] = "unhealthy"
            service["last_check"] = datetime.now()
            service["error"] = str(e)
            
            # Cache the error status
            await cache.set(
                f"health:{name}",
                {
                    "status": service["status"],
                    "last_check": service["last_check"].isoformat(),
                    "error": str(e)
                },
                ttl=timedelta(minutes=5)
            )
            
            logger.error(f"Health check failed for {name}: {str(e)}")
            return False

    async def check_all(self) -> Dict:
        """
        Check health of all registered services
        """
        results = {}
        for name in self.services:
            results[name] = {
                "healthy": await self.check_service(name),
                "status": self.services[name]["status"],
                "last_check": self.services[name]["last_check"],
                "error": self.services[name]["error"]
            }
        return results

    async def start_monitoring(self):
        """
        Start continuous health monitoring
        """
        self._running = True
        while self._running:
            await self.check_all()
            await asyncio.sleep(self.check_interval)

    async def stop_monitoring(self):
        """
        Stop health monitoring
        """
        self._running = False

# Global health monitor instance
health_monitor = HealthMonitor() 