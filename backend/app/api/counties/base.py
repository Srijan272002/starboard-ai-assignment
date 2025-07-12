"""
Base classes for county API implementations
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
import httpx
import asyncio

from pydantic import BaseModel, Field


class PropertyData(BaseModel):
    """Standardized property data model"""
    property_id: str
    address: str
    city: str
    state: str
    zip_code: str
    property_type: str
    land_area: Optional[float] = None
    building_area: Optional[float] = None
    year_built: Optional[int] = None
    assessed_value: Optional[float] = None
    last_sale_date: Optional[str] = None
    last_sale_price: Optional[float] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class CountyAPI(ABC):
    """Base class for county API implementations"""
    
    def __init__(self, county_name: str):
        """Initialize county API"""
        self.county_name = county_name
        self.client = httpx.AsyncClient(timeout=30.0)
        self._cleanup_task = None
        
    @abstractmethod
    async def initialize(self):
        """Initialize API connection and verify access"""
        pass
        
    @abstractmethod
    async def get_property(self, property_id: str) -> Optional[PropertyData]:
        """Get property data by ID"""
        pass
        
    @abstractmethod
    async def search_properties(
        self,
        filters: Dict[str, Any] = None,
        limit: int = 100
    ) -> List[PropertyData]:
        """Search for properties with filters"""
        pass
        
    async def close(self):
        """Close API connection"""
        if self.client:
            await self.client.aclose()
            self.client = None
        
    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.client and not self._cleanup_task:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    self._cleanup_task = loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except Exception:
                pass  # Ignore cleanup errors during shutdown 