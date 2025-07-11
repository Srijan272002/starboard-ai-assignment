"""
Base County API - Common interface for all county API implementations
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime
import structlog
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import StarboardException
from app.api.discovery import APIAnalyzer, AuthenticationHandler, RateLimiter, APIHealthMonitor, BatchingStrategy

logger = structlog.get_logger(__name__)


class PropertySearchParams(BaseModel):
    """Parameters for property search"""
    address: Optional[str] = None
    property_id: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    property_type: Optional[str] = None
    min_square_footage: Optional[float] = None
    max_square_footage: Optional[float] = None
    min_assessed_value: Optional[float] = None
    max_assessed_value: Optional[float] = None
    limit: int = 100
    offset: int = 0


class StandardizedProperty(BaseModel):
    """Standardized property data model"""
    property_id: str
    county: str
    address: str
    city: str
    state: str
    zip_code: Optional[str] = None
    
    # Property details
    property_type: Optional[str] = None
    zoning: Optional[str] = None
    square_footage: Optional[float] = None
    lot_size: Optional[float] = None
    year_built: Optional[int] = None
    
    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Financial
    assessed_value: Optional[float] = None
    market_value: Optional[float] = None
    tax_amount: Optional[float] = None
    
    # Features and metadata
    features: Dict[str, Any] = Field(default_factory=dict)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    data_quality_score: float = 0.0
    confidence_score: float = 0.0
    
    # Processing metadata
    source_api: str
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class APIResponse(BaseModel):
    """Response from county API"""
    success: bool
    data: List[Dict[str, Any]] = Field(default_factory=list)
    total_records: int = 0
    error_message: Optional[str] = None
    response_time_ms: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseCountyAPI(ABC):
    """Abstract base class for county API implementations"""
    
    def __init__(self, county_name: str):
        self.county_name = county_name
        self.analyzer = APIAnalyzer()
        self.auth_handler = AuthenticationHandler()
        self.rate_limiter = RateLimiter()
        self.health_monitor = APIHealthMonitor()
        self.batch_strategy = BatchingStrategy()
        
        # County-specific configuration
        self._setup_county_config()
        
        # Initialize components
        self._initialize_components()
        
        logger.info("County API initialized", county=county_name)
    
    @abstractmethod
    def _setup_county_config(self):
        """Setup county-specific configuration"""
        pass
    
    @abstractmethod
    async def _authenticate(self) -> Dict[str, str]:
        """Get authentication headers for requests"""
        pass
    
    @abstractmethod
    async def _search_properties_raw(
        self,
        params: PropertySearchParams
    ) -> APIResponse:
        """Search properties using raw county API"""
        pass
    
    @abstractmethod
    def _standardize_property(self, raw_data: Dict[str, Any]) -> StandardizedProperty:
        """Convert raw property data to standardized format"""
        pass
    
    @abstractmethod
    def _get_field_mappings(self) -> Dict[str, str]:
        """Get field mappings for this county's API"""
        pass
    
    def _initialize_components(self):
        """Initialize discovery components"""
        # Configure authentication
        self.auth_config = self.auth_handler.get_county_auth_config(self.county_name)
        
        # Configure rate limiting
        self.rate_limiter.configure_rate_limit(
            api_name=f"{self.county_name}_api",
            county=self.county_name
        )
        
        # Setup health monitoring
        if hasattr(self, 'health_endpoint'):
            import asyncio
            asyncio.create_task(self.health_monitor.add_api_for_monitoring(
                api_name=f"{self.county_name}_api",
                health_endpoint=self.health_endpoint,
                county=self.county_name
            ))
        
        # Setup batching
        from app.api.discovery.batch_strategy import BatchConfig, BatchStrategy as BatchStrategyEnum
        batch_config = BatchConfig(
            strategy=BatchStrategyEnum.ADAPTIVE,
            max_batch_size=getattr(settings, f"{self.county_name.upper()}_COUNTY_BATCH_SIZE", 50),
            max_wait_time=30.0
        )
        self.batch_strategy.create_queue(f"{self.county_name}_search", batch_config)
    
    async def search_properties(
        self,
        params: PropertySearchParams
    ) -> List[StandardizedProperty]:
        """
        Search for properties with standardized output
        
        Args:
            params: Search parameters
            
        Returns:
            List of standardized property objects
        """
        logger.info("Searching properties", 
                   county=self.county_name,
                   params=params.dict(exclude_none=True))
        
        try:
            # Check rate limiting
            await self.rate_limiter.wait_if_needed(f"{self.county_name}_api")
            
            # Perform search
            response = await self._search_properties_raw(params)
            
            if not response.success:
                raise StarboardException(f"Search failed: {response.error_message}")
            
            # Standardize results
            standardized_properties = []
            for raw_property in response.data:
                try:
                    standardized = self._standardize_property(raw_property)
                    standardized_properties.append(standardized)
                except Exception as e:
                    logger.warning("Failed to standardize property", 
                                  county=self.county_name,
                                  error=str(e),
                                  raw_data=raw_property)
                    continue
            
            logger.info("Property search completed", 
                       county=self.county_name,
                       results_found=len(standardized_properties),
                       response_time=response.response_time_ms)
            
            return standardized_properties
            
        except Exception as e:
            logger.error("Property search failed", 
                        county=self.county_name,
                        error=str(e))
            raise StarboardException(f"Property search failed for {self.county_name}: {str(e)}")
    
    async def get_property_by_id(self, property_id: str) -> Optional[StandardizedProperty]:
        """
        Get a specific property by ID
        
        Args:
            property_id: Property identifier
            
        Returns:
            Standardized property object or None if not found
        """
        params = PropertySearchParams(property_id=property_id, limit=1)
        results = await self.search_properties(params)
        return results[0] if results else None
    
    async def batch_search_properties(
        self,
        search_requests: List[PropertySearchParams]
    ) -> List[List[StandardizedProperty]]:
        """
        Perform batch property searches
        
        Args:
            search_requests: List of search parameters
            
        Returns:
            List of property lists (one per search request)
        """
        async def batch_processor(batch_requests):
            results = []
            for request in batch_requests:
                search_params = request.data
                properties = await self.search_properties(search_params)
                results.append(properties)
            return results
        
        # Register batch processor if not already done
        queue_name = f"{self.county_name}_search"
        if queue_name not in self.batch_strategy.processors:
            self.batch_strategy.register_processor(queue_name, batch_processor)
        
        # Add requests to batch
        batch_ids = []
        for i, params in enumerate(search_requests):
            batch_id = await self.batch_strategy.add_request(
                queue_name=queue_name,
                request_id=f"search_{i}_{datetime.utcnow().timestamp()}",
                data=params
            )
            if batch_id:
                batch_ids.append(batch_id)
        
        # Wait for all batches to complete
        results = []
        for batch_id in batch_ids:
            if batch_id:
                batch_result = await self.batch_strategy.wait_for_batch(batch_id)
                results.extend(batch_result.results)
        
        return results
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to the county API
        
        Returns:
            Connection test results
        """
        logger.info("Testing API connection", county=self.county_name)
        
        try:
            # Perform a simple search to test connectivity
            test_params = PropertySearchParams(limit=1)
            start_time = datetime.utcnow()
            
            response = await self._search_properties_raw(test_params)
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Test authentication if required
            auth_valid = True
            if self.auth_config.auth_type.value != "none":
                try:
                    auth_headers = await self.auth_handler.get_auth_headers(self.auth_config)
                    auth_valid = len(auth_headers) > 0
                except:
                    auth_valid = False
            
            # Get rate limit status
            rate_limit_status = await self.rate_limiter.get_rate_limit_status(f"{self.county_name}_api")
            
            return {
                "county": self.county_name,
                "connection_success": response.success,
                "response_time_ms": int(response_time),
                "authentication_valid": auth_valid,
                "rate_limit_status": rate_limit_status,
                "api_endpoints_available": hasattr(self, 'base_url'),
                "data_available": len(response.data) > 0 if response.success else False,
                "error_message": response.error_message if not response.success else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Connection test failed", county=self.county_name, error=str(e))
            return {
                "county": self.county_name,
                "connection_success": False,
                "error_message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def calculate_data_quality_score(self, property_data: StandardizedProperty) -> float:
        """
        Calculate data quality score for a property
        
        Args:
            property_data: Standardized property data
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        score = 0.0
        max_score = 1.0
        
        # Essential fields (60% of score)
        essential_fields = ['property_id', 'address', 'city', 'county']
        essential_score = sum(1 for field in essential_fields if getattr(property_data, field))
        score += (essential_score / len(essential_fields)) * 0.6
        
        # Important fields (30% of score)
        important_fields = ['property_type', 'square_footage', 'assessed_value']
        important_score = sum(1 for field in important_fields if getattr(property_data, field))
        score += (important_score / len(important_fields)) * 0.3
        
        # Nice-to-have fields (10% of score)
        nice_to_have = ['year_built', 'lot_size', 'latitude', 'longitude']
        nice_score = sum(1 for field in nice_to_have if getattr(property_data, field))
        score += (nice_score / len(nice_to_have)) * 0.1
        
        return min(score, max_score)
    
    async def get_api_status(self) -> Dict[str, Any]:
        """Get comprehensive API status"""
        health_status = self.health_monitor.get_api_health_status(f"{self.county_name}_api")
        rate_limit_status = await self.rate_limiter.get_rate_limit_status(f"{self.county_name}_api")
        batch_status = self.batch_strategy.get_queue_status(f"{self.county_name}_search")
        
        return {
            "county": self.county_name,
            "health": health_status,
            "rate_limiting": rate_limit_status,
            "batching": batch_status,
            "field_mappings": self._get_field_mappings(),
            "last_updated": datetime.utcnow().isoformat()
        }
    
    async def close(self):
        """Close all connections and cleanup resources"""
        logger.info("Closing county API", county=self.county_name)
        
        await self.analyzer.close()
        await self.rate_limiter.close()
        await self.health_monitor.close()
        await self.batch_strategy.close()
        
        logger.info("County API closed", county=self.county_name) 