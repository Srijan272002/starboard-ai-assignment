"""
LA County API Implementation
"""

from typing import Dict, List, Optional, Any
import structlog
from datetime import datetime

# from .base import BaseCountyAPI  # Simplified for now
from app.api.discovery.authentication import AuthType
from app.db.models import StandardizedProperty, PropertySearchParams

logger = structlog.get_logger(__name__)


class LACountyAPI:
    """LA County property data API implementation"""
    
    def __init__(self):
        self.county_name = "la"
        self.base_url = "https://data.lacounty.gov/resource/"
        self.api_endpoints = {
            "properties": "9trm-uz8i.json",  # Example Socrata dataset ID
            "assessments": "roll-ap6t.json",
            "sales": "sales-data.json"
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
        
        # Configure authentication for LA County
        self.auth_config = self.auth_handler.create_auth_config(
            auth_type=AuthType.API_KEY,
            county="la",
            api_key_header="X-App-Token"
        )
        
        logger.info("LA County API initialized")
    
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
        Search for properties in LA County
        
        Args:
            params: Search parameters
            
        Returns:
            List of standardized properties
        """
        try:
            # Build query parameters for LA County API
            query_params = await self._build_la_county_query(params)
            
            # Make the API request
            endpoint = "properties"
            raw_data = await self.make_request(endpoint, query_params)
            
            if not raw_data:
                return []
            
            # Process and standardize the data
            standardized_properties = []
            for raw_property in raw_data:
                try:
                    standardized_property = await self._standardize_la_county_property(raw_property)
                    if standardized_property:
                        standardized_properties.append(standardized_property)
                except Exception as e:
                    logger.warning("Failed to standardize LA County property", 
                                  property_data=raw_property,
                                  error=str(e))
                    continue
            
            logger.info("LA County properties retrieved", 
                       count=len(standardized_properties))
            
            return standardized_properties
            
        except Exception as e:
            logger.error("LA County property search failed", 
                        params=params.dict(),
                        error=str(e))
            return []
    
    async def _build_la_county_query(
        self,
        params: PropertySearchParams
    ) -> Dict[str, Any]:
        """Build query parameters for LA County API"""
        query = {}
        
        # Add limit
        if params.limit:
            query["$limit"] = min(params.limit, 2000)  # LA County API limit
        
        # Add offset
        if params.offset:
            query["$offset"] = params.offset
        
        # Build WHERE clause conditions
        where_conditions = []
        
        # Property type filter
        if params.property_type:
            # Map to LA County property type values
            la_county_types = {
                "warehouse": ["warehouse", "distribution center", "storage"],
                "industrial": ["industrial", "manufacturing", "factory"],
                "office": ["office", "commercial office"],
                "retail": ["retail", "commercial retail"],
                "flex_space": ["flex", "mixed use"]
            }
            
            county_types = la_county_types.get(params.property_type, [params.property_type])
            if county_types:
                type_conditions = " OR ".join([f"use_code_description ILIKE '%{t}%'" for t in county_types])
                where_conditions.append(f"({type_conditions})")
        
        # Size filter
        if params.min_size:
            where_conditions.append(f"square_footage >= {params.min_size}")
        if params.max_size:
            where_conditions.append(f"square_footage <= {params.max_size}")
        
        # Price filter
        if params.min_price:
            where_conditions.append(f"assessed_value >= {params.min_price}")
        if params.max_price:
            where_conditions.append(f"assessed_value <= {params.max_price}")
        
        # Location filter (ZIP code)
        if params.zip_code:
            where_conditions.append(f"mail_zip_code='{params.zip_code}'")
        
        # Combine WHERE conditions
        if where_conditions:
            query["$where"] = " AND ".join(where_conditions)
        
        # Add ordering
        query["$order"] = "assessed_value DESC"
        
        return query
    
    async def _standardize_la_county_property(
        self,
        raw_property: Dict[str, Any]
    ) -> Optional[StandardizedProperty]:
        """
        Standardize an LA County property record
        
        Args:
            raw_property: Raw property data from LA County API
            
        Returns:
            Standardized property or None if processing fails
        """
        try:
            # Map and normalize fields using field mapper
            mapped_data = self.field_mapper.map_fields(raw_property, "la")
            
            # Validate the mapped data
            validation_results = self.data_validator.validate_data(mapped_data)
            
            # Transform the data
            transformed_data = self.data_transformer.transform_data(mapped_data)
            
            # Create standardized property
            standardized_property = StandardizedProperty(
                property_id=transformed_data.get("property_id") or transformed_data.get("ain", ""),
                source="la_county",
                address=transformed_data.get("address", ""),
                city=transformed_data.get("city", ""),
                state="CA",
                zip_code=transformed_data.get("zip_code", ""),
                county="Los Angeles",
                property_type=transformed_data.get("property_type", "unknown"),
                square_feet=self._safe_float(transformed_data.get("square_feet")),
                price=self._safe_float(transformed_data.get("price") or transformed_data.get("assessed_value")),
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
            logger.error("LA County property standardization failed", 
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
            property_id: Property identifier (AIN)
            
        Returns:
            Detailed property information or None
        """
        try:
            # Query for specific property
            query_params = {
                "$where": f"ain='{property_id}'",
                "$limit": 1
            }
            
            raw_data = await self.make_request("properties", query_params)
            
            if raw_data and len(raw_data) > 0:
                return await self._standardize_la_county_property(raw_data[0])
            
            return None
            
        except Exception as e:
            logger.error("LA County property details failed", 
                        property_id=property_id,
                        error=str(e))
            return None
    
    async def get_available_filters(self) -> Dict[str, List[str]]:
        """Get available filter values for LA County"""
        try:
            # Get distinct values for common filter fields
            filters = {}
            
            # Property types
            type_query = {"$select": "DISTINCT use_code_description", "$limit": 100}
            type_data = await self.make_request("properties", type_query)
            if type_data:
                filters["property_types"] = [
                    item.get("use_code_description") 
                    for item in type_data 
                    if item.get("use_code_description")
                ]
            
            # ZIP codes
            zip_query = {"$select": "DISTINCT mail_zip_code", "$limit": 500}
            zip_data = await self.make_request("properties", zip_query)
            if zip_data:
                filters["zip_codes"] = [
                    item.get("mail_zip_code") 
                    for item in zip_data 
                    if item.get("mail_zip_code") and len(str(item.get("mail_zip_code", ""))) == 5
                ]
            
            # Cities
            city_query = {"$select": "DISTINCT situs_city", "$limit": 200}
            city_data = await self.make_request("properties", city_query)
            if city_data:
                filters["cities"] = [
                    item.get("situs_city") 
                    for item in city_data 
                    if item.get("situs_city")
                ]
            
            return filters
            
        except Exception as e:
            logger.error("LA County filters retrieval failed", error=str(e))
            return {}
    
    async def test_connection(self) -> bool:
        """Test connection to LA County API"""
        try:
            # Make a simple test request
            test_params = {"$limit": 1}
            result = await self.make_request("properties", test_params)
            
            success = result is not None
            
            if success:
                logger.info("LA County API connection test successful")
            else:
                logger.warning("LA County API connection test failed")
            
            return success
            
        except Exception as e:
            logger.error("LA County API connection test error", error=str(e))
            return False 