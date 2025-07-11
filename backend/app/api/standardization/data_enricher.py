"""
Data Enricher - Data enrichment and augmentation system
"""

from typing import Any, Dict, List, Optional, Union
import structlog
from pydantic import BaseModel
from datetime import datetime
import aiohttp
import json

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class EnrichmentSource(BaseModel):
    """Configuration for an enrichment source"""
    name: str
    type: str  # "api", "database", "calculation"
    enabled: bool = True
    priority: int = 0
    config: Dict[str, Any] = {}


class EnrichmentResult(BaseModel):
    """Result of data enrichment operation"""
    source: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    timestamp: datetime = datetime.utcnow()


class DataEnricher:
    """Data enrichment and augmentation system"""
    
    def __init__(self):
        self.sources: Dict[str, EnrichmentSource] = {}
        self._load_default_sources()
        logger.info("Data enricher initialized")
    
    def _load_default_sources(self):
        """Load default enrichment sources"""
        # Geocoding enrichment
        self.add_source(EnrichmentSource(
            name="geocoding",
            type="api",
            priority=1,
            config={
                "api_url": "https://api.geocoding.service/v1/geocode",
                "api_key": settings.GEOCODING_API_KEY
            }
        ))
        
        # Property details enrichment
        self.add_source(EnrichmentSource(
            name="property_details",
            type="database",
            priority=2,
            config={
                "table": "property_details",
                "match_fields": ["property_id", "address"]
            }
        ))
        
        # Market data enrichment
        self.add_source(EnrichmentSource(
            name="market_data",
            type="api",
            priority=3,
            config={
                "api_url": "https://api.market-data.service/v1/properties",
                "api_key": settings.MARKET_DATA_API_KEY
            }
        ))
        
        # Calculated metrics
        self.add_source(EnrichmentSource(
            name="metrics",
            type="calculation",
            priority=4,
            config={
                "metrics": [
                    "price_per_sqft",
                    "occupancy_rate",
                    "market_comparison"
                ]
            }
        ))
    
    def add_source(self, source: EnrichmentSource):
        """Add an enrichment source"""
        self.sources[source.name] = source
    
    async def enrich_data(
        self,
        data: Dict[str, Any],
        sources: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[EnrichmentResult]]:
        """
        Enrich data using configured sources
        
        Args:
            data: Data to enrich
            sources: Optional list of specific sources to use
            context: Optional context data for enrichment
            
        Returns:
            Dictionary of enrichment results by source
        """
        results = {}
        
        # Get active sources
        active_sources = []
        for name, source in self.sources.items():
            if source.enabled and (not sources or name in sources):
                active_sources.append(source)
        
        # Sort by priority
        active_sources.sort(key=lambda s: s.priority)
        
        # Apply enrichments
        for source in active_sources:
            try:
                if source.type == "api":
                    result = await self._enrich_from_api(source, data, context)
                elif source.type == "database":
                    result = await self._enrich_from_database(source, data, context)
                elif source.type == "calculation":
                    result = await self._enrich_from_calculation(source, data, context)
                else:
                    logger.warning("Unknown enrichment source type", source_type=source.type)
                    continue
                
                results[source.name] = result
                
                # Update data with successful enrichments
                if result.success and result.data:
                    data.update(result.data)
                
            except Exception as e:
                logger.error("Enrichment failed",
                           source=source.name,
                           error=str(e))
                results[source.name] = EnrichmentResult(
                    source=source.name,
                    success=False,
                    errors=[str(e)]
                )
        
        return results
    
    async def _enrich_from_api(
        self,
        source: EnrichmentSource,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> EnrichmentResult:
        """Enrich data using API source"""
        try:
            api_url = source.config["api_url"]
            api_key = source.config.get("api_key")
            
            # Prepare request
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    json=data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        enriched_data = await response.json()
                        return EnrichmentResult(
                            source=source.name,
                            success=True,
                            data=enriched_data
                        )
                    else:
                        error_msg = await response.text()
                        return EnrichmentResult(
                            source=source.name,
                            success=False,
                            errors=[f"API error: {error_msg}"]
                        )
                        
        except Exception as e:
            return EnrichmentResult(
                source=source.name,
                success=False,
                errors=[f"API enrichment failed: {str(e)}"]
            )
    
    async def _enrich_from_database(
        self,
        source: EnrichmentSource,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> EnrichmentResult:
        """Enrich data using database source"""
        try:
            table = source.config["table"]
            match_fields = source.config["match_fields"]
            
            # Build query conditions
            conditions = []
            for field in match_fields:
                if field in data:
                    conditions.append(f"{field} = :{field}")
            
            if not conditions:
                return EnrichmentResult(
                    source=source.name,
                    success=False,
                    errors=["No matching fields found"]
                )
            
            # Execute query
            # This would use your database connection
            # For now, return empty success
            return EnrichmentResult(
                source=source.name,
                success=True,
                data={}
            )
            
        except Exception as e:
            return EnrichmentResult(
                source=source.name,
                success=False,
                errors=[f"Database enrichment failed: {str(e)}"]
            )
    
    async def _enrich_from_calculation(
        self,
        source: EnrichmentSource,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> EnrichmentResult:
        """Enrich data using calculations"""
        try:
            metrics = source.config["metrics"]
            calculated_data = {}
            
            for metric in metrics:
                if metric == "price_per_sqft":
                    if data.get("price") and data.get("square_feet"):
                        calculated_data["price_per_sqft"] = (
                            data["price"] / data["square_feet"]
                        )
                
                elif metric == "occupancy_rate":
                    if data.get("occupied_space") and data.get("total_space"):
                        calculated_data["occupancy_rate"] = (
                            data["occupied_space"] / data["total_space"]
                        )
                
                elif metric == "market_comparison":
                    if context and context.get("market_avg_price"):
                        if data.get("price"):
                            calculated_data["price_vs_market"] = (
                                data["price"] / context["market_avg_price"]
                            )
            
            return EnrichmentResult(
                source=source.name,
                success=True,
                data=calculated_data
            )
            
        except Exception as e:
            return EnrichmentResult(
                source=source.name,
                success=False,
                errors=[f"Calculation enrichment failed: {str(e)}"]
            ) 