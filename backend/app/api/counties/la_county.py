"""
Los Angeles County API Integration
"""

import yaml
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import os

import structlog
from pydantic import BaseModel

from ..discovery.api_analyzer import APIAnalyzer
from ..discovery.authentication import AuthenticationHandler
from ..discovery.rate_limiter import RateLimiter
from .base import CountyAPI, PropertyData
from app.core.config import settings

logger = structlog.get_logger(__name__)


class LACountyAPI(CountyAPI):
    """Los Angeles County API implementation"""
    
    def __init__(self):
        super().__init__("la_county")
        self.api_analyzer = APIAnalyzer()
        self.auth_handler = AuthenticationHandler()
        self.rate_limiter = RateLimiter()
        
        # Load configuration
        current_dir = Path(__file__).resolve().parent
        # Navigate up to the backend directory (not the project root)
        backend_dir = current_dir.parent.parent.parent
        config_path = backend_dir / "config" / "field_mappings.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        with open(config_path) as f:
            self.config = yaml.safe_load(f)["la_county"]
            
        # Configure API components
        self.base_url = self.config["base_url"]
        self.endpoints = self.config["endpoints"]
        self.field_mappings = self.config["field_mappings"]
        
        # Set up rate limiting
        self.rate_limiter.configure_rate_limit(
            "la_county",
            county="los_angeles"
        )
        
    async def initialize(self):
        """Initialize API connection and verify access"""
        logger.info("Initializing LA County API connection")
        
        try:
            # Analyze API
            analysis = await self.api_analyzer.discover_api(
                self.base_url,
                "la_county"
            )
            
            # Validate endpoints
            for endpoint_name, endpoint_path in self.endpoints.items():
                if not any(ep.url.endswith(endpoint_path) for ep in analysis.discovered_endpoints):
                    logger.warning(
                        "Endpoint not found in API discovery",
                        endpoint_name=endpoint_name,
                        endpoint_path=endpoint_path
                    )
            
            # Set up authentication - make it optional for development
            try:
                auth_config = self.auth_handler.get_county_auth_config("los_angeles")
                test_url = f"{self.base_url}{self.endpoints['properties']}"
                
                if not await self.auth_handler.validate_authentication(auth_config, test_url):
                    logger.warning("LA County API authentication failed. Some features may not work correctly.")
            except Exception as auth_error:
                logger.warning(
                    "LA County API authentication setup failed. Running in development mode.",
                    error=str(auth_error)
                )
                
            logger.info("LA County API initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize LA County API", error=str(e))
            # Don't raise the exception to allow the application to start
            # raise
            
    async def get_property(self, property_id: str) -> Optional[PropertyData]:
        """Get property data by ID"""
        try:
            # Check rate limit
            await self.rate_limiter.wait_if_needed("la_county")
            
            # Get auth headers
            auth_config = self.auth_handler.get_county_auth_config("los_angeles")
            headers = await self.auth_handler.get_auth_headers(auth_config)
            
            # Make request
            url = f"{self.base_url}{self.endpoints['properties']}"
            params = {
                "ain": property_id
            }
            
            async with self.client as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                if not data:
                    return None
                    
                # Map fields
                property_data = self._map_property_data(data)
                
                # Get additional data
                assessment_data = await self._get_assessment_data(property_id)
                sales_data = await self._get_sales_data(property_id)
                
                if assessment_data:
                    property_data.update(assessment_data)
                if sales_data:
                    property_data.update(sales_data)
                    
                return PropertyData(**property_data)
                
        except Exception as e:
            logger.error(
                "Failed to get LA County property",
                property_id=property_id,
                error=str(e)
            )
            return None
            
    async def search_properties(
        self,
        filters: Dict[str, Any] = None,
        limit: int = 100
    ) -> List[PropertyData]:
        """Search for properties with filters"""
        try:
            # Check rate limit
            await self.rate_limiter.wait_if_needed("la_county")
            
            # Get auth headers
            try:
                auth_config = self.auth_handler.get_county_auth_config("los_angeles")
                headers = await self.auth_handler.get_auth_headers(auth_config)
            except Exception as auth_error:
                logger.error(
                    "Authentication failed when attempting to access LA County API",
                    error=str(auth_error)
                )
                # Check if we're forcing real API usage
                if settings.REAL_API_REQUIRED:
                    raise Exception("Real API access is required but authentication failed: " + str(auth_error))
                else:
                    # Only use mock data if explicitly allowed
                    if settings.ENVIRONMENT == "development" and settings.ALLOW_MOCK_DATA:
                        logger.warning("Using mock data as fallback in development mode")
                        return self._get_mock_properties(limit)
                    else:
                        # In production or when mock data is not allowed, we should fail properly
                        raise
            
            # Build query
            where_clauses = []
            if filters:
                for key, value in filters.items():
                    field = self.field_mappings.get(key)
                    if field:
                        if isinstance(value, str):
                            where_clauses.append(f"{field}='{value}'")
                        else:
                            where_clauses.append(f"{field}={value}")
                            
            # Make request
            url = f"{self.base_url}{self.endpoints['properties']}"
            params = {
                "$where": " AND ".join(where_clauses) if where_clauses else None,
                "$limit": limit
            }
            
            async with self.client as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # Map results
                properties = []
                for item in data:
                    try:
                        property_data = self._map_property_data(item)
                        properties.append(PropertyData(**property_data))
                    except Exception as e:
                        logger.warning(
                            "Failed to parse property data",
                            error=str(e),
                            data=item
                        )
                        continue
                        
                return properties
                
        except Exception as e:
            logger.error(
                "Failed to search LA County properties",
                filters=filters,
                error=str(e)
            )
            # Only use mock data if explicitly allowed and not in production
            if settings.ENVIRONMENT == "development" and settings.ALLOW_MOCK_DATA and not settings.REAL_API_REQUIRED:
                logger.info("Returning mock data in development mode")
                return self._get_mock_properties(limit)
            # Otherwise, propagate the error
            raise Exception(f"Failed to fetch real property data from LA County API: {str(e)}")
            
    async def _get_assessment_data(self, property_id: str) -> Optional[Dict[str, Any]]:
        """Get assessment data for a property"""
        try:
            # Check rate limit
            await self.rate_limiter.wait_if_needed("la_county")
            
            # Get auth headers
            auth_config = self.auth_handler.get_county_auth_config("los_angeles")
            headers = await self.auth_handler.get_auth_headers(auth_config)
            
            # Make request
            url = f"{self.base_url}{self.endpoints['assessments']}"
            params = {
                "ain": property_id,
                "format": "json"
            }
            
            async with self.client as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                if not data:
                    return None
                    
                return self._map_assessment_data(data)
                
        except Exception as e:
            logger.error(
                "Failed to get assessment data",
                property_id=property_id,
                error=str(e)
            )
            return None
            
    async def _get_sales_data(self, property_id: str) -> Optional[Dict[str, Any]]:
        """Get sales history for a property"""
        try:
            # Check rate limit
            await self.rate_limiter.wait_if_needed("la_county")
            
            # Get auth headers
            auth_config = self.auth_handler.get_county_auth_config("los_angeles")
            headers = await self.auth_handler.get_auth_headers(auth_config)
            
            # Make request
            url = f"{self.base_url}{self.endpoints['sales']}"
            params = {
                "ain": property_id,
                "format": "json"
            }
            
            async with self.client as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                if not data:
                    return None
                    
                return self._map_sales_data(data)
                
        except Exception as e:
            logger.error(
                "Failed to get sales data",
                property_id=property_id,
                error=str(e)
            )
            return None
            
    def _map_property_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map raw property data to standardized fields"""
        mapped_data = {}
        
        for target_field, source_field in self.field_mappings.items():
            if source_field in data:
                mapped_data[target_field] = data[source_field]
                
        return mapped_data
        
    def _map_assessment_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map assessment data to standardized fields"""
        return {
            "assessed_value": float(data.get("total_value", 0)),
            "assessment_year": int(data.get("assessment_year", datetime.now().year))
        }
        
    def _map_sales_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map sales data to standardized fields"""
        return {
            "last_sale_date": data.get("recording_date"),
            "last_sale_price": float(data.get("sale_amount", 0))
        } 

    def _get_mock_properties(self, limit: int = 10) -> List[PropertyData]:
        """Generate mock property data for development"""
        import random
        from datetime import datetime, timedelta
        
        mock_properties = []
        
        # Property types
        property_types = ["Residential", "Commercial", "Industrial", "Land"]
        
        # Street names
        streets = ["Main St", "Sunset Blvd", "Hollywood Blvd", "Wilshire Blvd", "Venice Blvd"]
        
        # Cities
        cities = ["Los Angeles", "Santa Monica", "Pasadena", "Beverly Hills", "Long Beach"]
        
        # Generate random properties
        for i in range(min(limit, 20)):  # Cap at 20 mock properties
            # Generate a random date in the past 5 years
            days_back = random.randint(1, 365 * 5)
            sale_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            
            # Generate a random property
            property_data = {
                "property_id": f"MOCK-{i+1:06d}",
                "address": f"{random.randint(100, 9999)} {random.choice(streets)}",
                "city": random.choice(cities),
                "state": "CA",
                "zip_code": f"900{random.randint(10, 99)}",
                "property_type": random.choice(property_types),
                "land_area": round(random.uniform(0.1, 2.0), 2),
                "building_area": round(random.uniform(1000, 5000), 0),
                "year_built": random.randint(1950, 2020),
                "assessed_value": round(random.uniform(100000, 1000000), 0),
                "last_sale_date": sale_date,
                "last_sale_price": round(random.uniform(200000, 2000000), 0),
                "raw_data": {"mock": True},
                "last_updated": datetime.utcnow()
            }
            
            mock_properties.append(PropertyData(**property_data))
            
        return mock_properties 