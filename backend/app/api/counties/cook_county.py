"""
Cook County API Implementation
"""

from typing import Dict, List, Optional, Any
import structlog
from datetime import datetime

# from .base import BaseCountyAPI  # Simplified for now
from app.api.discovery.authentication import AuthType
from app.db.models import StandardizedProperty, PropertySearchParams

logger = structlog.get_logger(__name__)


class CookCountyAPI:
    """Cook County property data API implementation"""
    
    def __init__(self):
        self.county_name = "cook"
        self.base_url = "https://datacatalog.cookcountyil.gov/resource/"
        self.api_endpoints = {
            "properties": "bcnq-qi2z.json",  # Example endpoint ID
            "assessments": "7pny-nedm.json",
            "sales": "wvhk-k5uv.json"
        }
        
        # Initialize discovery components
        from app.api.discovery import APIAnalyzer, AuthenticationHandler, RateLimiter
        from app.api.standardization import FieldMapper, DataValidator, DataTransformer
        
        self.api_analyzer = APIAnalyzer()
        self.auth_handler = AuthenticationHandler()
        self.rate_limiter = RateLimiter()
        self.field_mapper = FieldMapper()
        self.data_validator = DataValidator()
        self.data_transformer = DataTransformer()
        
        # Configure authentication for Cook County
        self.auth_config = self.auth_handler.create_auth_config(
            auth_type=AuthType.API_KEY,
            county="cook",
            api_key_header="X-App-Token",
            api_key_param="$$app_token"
        )
        
        logger.info("Cook County API initialized")
    
    async def make_request(self, endpoint: str, params: dict = None):
        """Make HTTP request to county API"""
        import httpx
        
        url = f"{self.base_url}{self.api_endpoints.get(endpoint, endpoint)}"
        headers = await self.auth_handler.get_auth_headers(self.auth_config)
        auth_params = await self.auth_handler.get_auth_params(self.auth_config)
        
        # Merge auth params with request params
        all_params = {**(params or {}), **auth_params}
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers, params=all_params)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error("API request failed", 
                        county=self.county_name,
                        endpoint=endpoint,
                        error=str(e))
            return None
    
    async def search_properties(
        self,
        params: PropertySearchParams
    ) -> List[StandardizedProperty]:
        """
        Search for properties in Cook County
        
        Args:
            params: Search parameters
            
        Returns:
            List of standardized properties
        """
        try:
            # Build query parameters for Cook County API
            query_params = await self._build_cook_county_query(params)
            
            # Make the API request
            endpoint = "properties"
            raw_data = await self.make_request(endpoint, query_params)
            
            if not raw_data:
                return []
            
            # Process and standardize the data
            standardized_properties = []
            for raw_property in raw_data:
                try:
                    standardized_property = await self._standardize_cook_county_property(raw_property)
                    if standardized_property:
                        standardized_properties.append(standardized_property)
                except Exception as e:
                    logger.warning("Failed to standardize Cook County property", 
                                  property_data=raw_property,
                                  error=str(e))
                    continue
            
            logger.info("Cook County properties retrieved", 
                       count=len(standardized_properties))
            
            return standardized_properties
            
        except Exception as e:
            logger.error("Cook County property search failed", 
                        params=params.dict(),
                        error=str(e))
            return []
    
    async def _build_cook_county_query(
        self,
        params: PropertySearchParams
    ) -> Dict[str, Any]:
        """Build query parameters for Cook County API"""
        query = {}
        
        # Add limit
        if params.limit:
            query["$limit"] = min(params.limit, 1000)  # Cook County API limit
        
        # Add offset
        if params.offset:
            query["$offset"] = params.offset
        
        # Build WHERE clause conditions
        where_conditions = []
        
        # Property type filter
        if params.property_type:
            # Map to Cook County property type values
            cook_county_types = {
                "warehouse": ["warehouse", "distribution"],
                "industrial": ["industrial", "manufacturing"],
                "office": ["office"],
                "retail": ["retail"],
                "flex_space": ["flex"]
            }
            
            county_types = cook_county_types.get(params.property_type, [params.property_type])
            if county_types:
                type_conditions = " OR ".join([f"property_class='{t}'" for t in county_types])
                where_conditions.append(f"({type_conditions})")
        
        # Size filter
        if params.min_size:
            where_conditions.append(f"square_footage >= {params.min_size}")
        if params.max_size:
            where_conditions.append(f"square_footage <= {params.max_size}")
        
        # Price filter
        if params.min_price:
            where_conditions.append(f"market_value >= {params.min_price}")
        if params.max_price:
            where_conditions.append(f"market_value <= {params.max_price}")
        
        # Location filter (ZIP code)
        if params.zip_code:
            where_conditions.append(f"zip_code='{params.zip_code}'")
        
        # Combine WHERE conditions
        if where_conditions:
            query["$where"] = " AND ".join(where_conditions)
        
        # Add ordering
        query["$order"] = "market_value DESC"
        
        return query
    
    async def _standardize_cook_county_property(
        self,
        raw_property: Dict[str, Any]
    ) -> Optional[StandardizedProperty]:
        """
        Standardize a Cook County property record
        
        Args:
            raw_property: Raw property data from Cook County API
            
        Returns:
            Standardized property or None if processing fails
        """
        try:
            # Map and normalize fields using field mapper
            mapped_data = self.field_mapper.map_fields(raw_property, "cook")
            
            # Validate the mapped data
            validation_results = self.data_validator.validate_data(mapped_data)
            
            # Transform the data
            transformed_data = self.data_transformer.transform_data(mapped_data)
            
            # Create standardized property
            standardized_property = StandardizedProperty(
                property_id=transformed_data.get("property_id") or transformed_data.get("pin", ""),
                source="cook_county",
                address=transformed_data.get("address", ""),
                city=transformed_data.get("city", ""),
                state="IL",
                zip_code=transformed_data.get("zip_code", ""),
                county="Cook",
                property_type=transformed_data.get("property_type", "unknown"),
                square_feet=self._safe_float(transformed_data.get("square_feet")),
                price=self._safe_float(transformed_data.get("price") or transformed_data.get("market_value")),
                price_per_sqft=self._safe_float(transformed_data.get("price_per_sqft")),
                year_built=self._safe_int(transformed_data.get("year_built")),
                latitude=self._safe_float(transformed_data.get("latitude")),
                longitude=self._safe_float(transformed_data.get("longitude")),
                description=transformed_data.get("description", ""),
                listing_url=transformed_data.get("listing_url"),
                contact_info=transformed_data.get("contact_info"),
                last_updated=datetime.utcnow(),
                raw_data=raw_property,
                data_quality_score=self.data_validator.get_data_quality_score(validation_results)
            )
            
            return standardized_property
            
        except Exception as e:
            logger.error("Cook County property standardization failed", 
                        raw_property=raw_property,
                        error=str(e))
            return None
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float"""
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert value to int"""
        try:
            if value is None or value == "":
                return None
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    async def get_property_details(
        self,
        property_id: str
    ) -> Optional[StandardizedProperty]:
        """
        Get detailed information for a specific property
        
        Args:
            property_id: Property identifier
            
        Returns:
            Detailed property information or None
        """
        try:
            # Query for specific property
            query_params = {
                "$where": f"pin='{property_id}'",
                "$limit": 1
            }
            
            raw_data = await self.make_request("properties", query_params)
            
            if raw_data and len(raw_data) > 0:
                return await self._standardize_cook_county_property(raw_data[0])
            
            return None
            
        except Exception as e:
            logger.error("Cook County property details failed", 
                        property_id=property_id,
                        error=str(e))
            return None
    
    async def get_available_filters(self) -> Dict[str, List[str]]:
        """Get available filter values for Cook County"""
        try:
            # Get distinct values for common filter fields
            filters = {}
            
            # Property types
            type_query = {"$select": "DISTINCT property_class", "$limit": 100}
            type_data = await self.make_request("properties", type_query)
            if type_data:
                filters["property_types"] = [item.get("property_class") for item in type_data if item.get("property_class")]
            
            # ZIP codes
            zip_query = {"$select": "DISTINCT zip_code", "$limit": 500}
            zip_data = await self.make_request("properties", zip_query)
            if zip_data:
                filters["zip_codes"] = [item.get("zip_code") for item in zip_data if item.get("zip_code")]
            
            return filters
            
        except Exception as e:
            logger.error("Cook County filters retrieval failed", error=str(e))
            return {}
    
    async def test_connection(self) -> bool:
        """Test connection to Cook County API"""
        try:
            # Make a simple test request
            test_params = {"$limit": 1}
            result = await self.make_request("properties", test_params)
            
            success = result is not None
            
            if success:
                logger.info("Cook County API connection test successful")
            else:
                logger.warning("Cook County API connection test failed")
            
            return success
            
        except Exception as e:
            logger.error("Cook County API connection test error", error=str(e))
            return False 