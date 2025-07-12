"""
API Analyzer - Core component for discovering and analyzing external APIs
"""

import asyncio
import json
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin, urlparse
import httpx
from pydantic import BaseModel, Field
import structlog

from app.core.config import settings
from app.core.exceptions import StarboardException
from .authentication import AuthenticationHandler
from .rate_limiter import RateLimiter

logger = structlog.get_logger(__name__)


class APIEndpoint(BaseModel):
    """Represents a discovered API endpoint"""
    url: str
    method: str = "GET"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = None
    response_schema: Optional[Dict[str, Any]] = None
    rate_limit: Optional[int] = None
    authentication_required: bool = False
    data_fields: List[str] = Field(default_factory=list)


class APIDocumentation(BaseModel):
    """API documentation template"""
    api_name: str
    base_url: str
    version: Optional[str] = None
    endpoints: List[APIEndpoint] = Field(default_factory=list)
    authentication: Dict[str, Any] = Field(default_factory=dict)
    rate_limits: Dict[str, Any] = Field(default_factory=dict)
    data_schema: Dict[str, Any] = Field(default_factory=dict)
    contact_info: Optional[Dict[str, str]] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    status: str = "unknown"  # active, inactive, rate_limited, error


class APIAnalysisResult(BaseModel):
    """Result of API analysis"""
    api_name: str
    documentation: APIDocumentation
    health_status: str
    discovered_endpoints: List[APIEndpoint]
    field_mappings: Dict[str, str] = Field(default_factory=dict)
    data_quality_score: float = 0.0
    recommendations: List[str] = Field(default_factory=list)
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)


class APIAnalyzer:
    """Main API analyzer for discovering and analyzing external APIs"""
    
    def __init__(self):
        self.auth_handler = AuthenticationHandler()
        self.rate_limiter = RateLimiter()
        self.client = httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT,
            limits=httpx.Limits(max_connections=settings.MAX_CONCURRENT_REQUESTS)
        )
        
    async def discover_api(self, base_url: str, api_name: str) -> APIAnalysisResult:
        """
        Discover and analyze an API
        
        Args:
            base_url: Base URL of the API
            api_name: Name identifier for the API
            
        Returns:
            APIAnalysisResult with discovered information
        """
        logger.info("Starting API discovery", api_name=api_name, base_url=base_url)
        
        try:
            # Initialize documentation
            documentation = APIDocumentation(
                api_name=api_name,
                base_url=base_url
            )
            
            # Discover endpoints
            endpoints = await self._discover_endpoints(base_url)
            documentation.endpoints = endpoints
            
            # Test API health
            health_status = await self._check_api_health(base_url)
            documentation.status = health_status
            
            # Analyze authentication requirements
            auth_info = await self._analyze_authentication(base_url)
            documentation.authentication = auth_info
            
            # Discover rate limits
            rate_limits = await self._discover_rate_limits(base_url)
            documentation.rate_limits = rate_limits
            
            # Analyze data schema
            data_schema = await self._analyze_data_schema(endpoints)
            documentation.data_schema = data_schema
            
            # Generate field mappings
            field_mappings = await self._generate_field_mappings(data_schema)
            
            # Calculate data quality score
            quality_score = await self._calculate_data_quality_score(data_schema)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(documentation, health_status)
            
            result = APIAnalysisResult(
                api_name=api_name,
                documentation=documentation,
                health_status=health_status,
                discovered_endpoints=endpoints,
                field_mappings=field_mappings,
                data_quality_score=quality_score,
                recommendations=recommendations
            )
            
            # Save documentation
            await self._save_documentation(documentation)
            
            logger.info("API discovery completed", 
                       api_name=api_name, 
                       endpoints_found=len(endpoints),
                       health_status=health_status,
                       quality_score=quality_score)
            
            return result
            
        except Exception as e:
            logger.error("API discovery failed", api_name=api_name, error=str(e))
            raise StarboardException(f"API discovery failed for {api_name}: {str(e)}")
    
    async def _discover_endpoints(self, base_url: str) -> List[APIEndpoint]:
        """Discover API endpoints through various methods"""
        endpoints = []
        
        # Try common endpoint discovery methods
        discovery_methods = [
            self._try_openapi_discovery,
            self._try_swagger_discovery,
            self._try_common_endpoints,
            self._try_directory_listing
        ]
        
        for method in discovery_methods:
            try:
                discovered = await method(base_url)
                endpoints.extend(discovered)
            except Exception as e:
                logger.debug("Endpoint discovery method failed", method=method.__name__, error=str(e))
                continue
        
        # Remove duplicates
        unique_endpoints = []
        seen_urls = set()
        for endpoint in endpoints:
            if endpoint.url not in seen_urls:
                unique_endpoints.append(endpoint)
                seen_urls.add(endpoint.url)
        
        return unique_endpoints
    
    async def _try_openapi_discovery(self, base_url: str) -> List[APIEndpoint]:
        """Try to discover endpoints via OpenAPI/Swagger spec"""
        endpoints = []
        openapi_paths = ["/openapi.json", "/swagger.json", "/api-docs", "/docs"]
        
        for path in openapi_paths:
            try:
                url = urljoin(base_url, path)
                response = await self.client.get(url)
                if response.status_code == 200:
                    spec = response.json()
                    endpoints.extend(self._parse_openapi_spec(spec, base_url))
                    break
            except:
                continue
                
        return endpoints
    
    async def _try_swagger_discovery(self, base_url: str) -> List[APIEndpoint]:
        """Try to discover endpoints via Swagger UI"""
        endpoints = []
        swagger_paths = ["/swagger-ui.html", "/swagger/", "/api/swagger-ui"]
        
        for path in swagger_paths:
            try:
                url = urljoin(base_url, path)
                response = await self.client.get(url)
                if response.status_code == 200:
                    # Parse HTML to find swagger config
                    endpoints.extend(self._parse_swagger_html(response.text, base_url))
                    break
            except:
                continue
                
        return endpoints
    
    async def _try_common_endpoints(self, base_url: str) -> List[APIEndpoint]:
        """Try common API endpoint patterns"""
        common_patterns = [
            "/api/v1/properties",
            "/api/properties", 
            "/properties",
            "/data/properties",
            "/parcels",
            "/assessments",
            "/real-estate",
            "/property-data",
            "/api/v1/search",
            "/search",
            "/query"
        ]
        
        endpoints = []
        for pattern in common_patterns:
            try:
                url = urljoin(base_url, pattern)
                response = await self.client.head(url)
                if response.status_code in [200, 405]:  # 405 means method not allowed but endpoint exists
                    endpoint = APIEndpoint(
                        url=url,
                        method="GET",
                        description=f"Common endpoint pattern: {pattern}"
                    )
                    endpoints.append(endpoint)
            except:
                continue
                
        return endpoints
    
    async def _try_directory_listing(self, base_url: str) -> List[APIEndpoint]:
        """Try to find endpoints through directory listing"""
        endpoints = []
        try:
            response = await self.client.get(base_url)
            if response.status_code == 200:
                # Parse HTML for links that might be endpoints
                endpoints.extend(self._parse_directory_html(response.text, base_url))
        except:
            pass
            
        return endpoints
    
    def _parse_openapi_spec(self, spec: Dict[str, Any], base_url: str) -> List[APIEndpoint]:
        """Parse OpenAPI specification to extract endpoints"""
        endpoints = []
        paths = spec.get("paths", {})
        
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    url = urljoin(base_url, path.lstrip("/"))
                    endpoint = APIEndpoint(
                        url=url,
                        method=method.upper(),
                        description=details.get("summary", ""),
                        parameters=details.get("parameters", {}),
                        response_schema=details.get("responses", {})
                    )
                    endpoints.append(endpoint)
        
        return endpoints
    
    def _parse_swagger_html(self, html: str, base_url: str) -> List[APIEndpoint]:
        """Parse Swagger UI HTML to extract endpoint information"""
        # This would need more sophisticated HTML parsing
        # For now, return empty list
        return []
    
    def _parse_directory_html(self, html: str, base_url: str) -> List[APIEndpoint]:
        """Parse directory listing HTML to find potential endpoints"""
        # This would need HTML parsing to find links
        # For now, return empty list
        return []
    
    async def _check_api_health(self, base_url: str) -> str:
        """Check API health status"""
        try:
            response = await self.client.get(base_url)
            if response.status_code == 200:
                return "active"
            elif response.status_code == 429:
                return "rate_limited"
            else:
                return "error"
        except:
            return "inactive"
    
    async def _analyze_authentication(self, base_url: str) -> Dict[str, Any]:
        """Analyze authentication requirements"""
        auth_info = {
            "required": False,
            "type": "none",
            "headers": [],
            "parameters": []
        }
        
        try:
            # Test without authentication
            response = await self.client.get(base_url)
            
            if response.status_code == 401:
                auth_info["required"] = True
                
                # Check common auth headers
                www_auth = response.headers.get("www-authenticate", "")
                if "bearer" in www_auth.lower():
                    auth_info["type"] = "bearer_token"
                elif "basic" in www_auth.lower():
                    auth_info["type"] = "basic_auth"
                elif "api" in www_auth.lower() or "key" in www_auth.lower():
                    auth_info["type"] = "api_key"
                    auth_info["headers"] = [settings.API_KEY_HEADER]
        except:
            pass
            
        return auth_info
    
    async def _discover_rate_limits(self, base_url: str) -> Dict[str, Any]:
        """Discover rate limiting information"""
        rate_limits = {
            "detected": False,
            "limits": {},
            "headers": []
        }
        
        try:
            response = await self.client.get(base_url)
            
            # Check for rate limit headers
            rate_limit_headers = [
                "x-ratelimit-limit",
                "x-ratelimit-remaining", 
                "x-ratelimit-reset",
                "x-rate-limit-limit",
                "x-rate-limit-remaining",
                "x-rate-limit-reset",
                "rate-limit-limit",
                "rate-limit-remaining"
            ]
            
            for header in rate_limit_headers:
                if header in response.headers:
                    rate_limits["detected"] = True
                    rate_limits["headers"].append(header)
                    rate_limits["limits"][header] = response.headers[header]
        except:
            pass
            
        return rate_limits
    
    async def _analyze_data_schema(self, endpoints: List[APIEndpoint]) -> Dict[str, Any]:
        """Analyze data schema from discovered endpoints"""
        schema = {
            "fields": [],
            "types": {},
            "patterns": {},
            "sample_data": {}
        }
        
        # Try to get sample data from endpoints
        for endpoint in endpoints[:3]:  # Limit to first 3 endpoints
            try:
                response = await self.client.get(endpoint.url)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        schema["sample_data"][endpoint.url] = data
                        # Extract field names
                        schema["fields"].extend(data.keys())
                    elif isinstance(data, list) and data:
                        schema["sample_data"][endpoint.url] = data[0]
                        if isinstance(data[0], dict):
                            schema["fields"].extend(data[0].keys())
            except:
                continue
        
        # Remove duplicates and analyze types
        schema["fields"] = list(set(schema["fields"]))
        
        return schema
    
    async def _generate_field_mappings(self, data_schema: Dict[str, Any]) -> Dict[str, str]:
        """Generate field mappings for standardization"""
        mappings = {}
        
        # Common property field patterns
        field_patterns = {
            "property_id": ["id", "parcel_id", "pin", "property_number", "assessment_id"],
            "address": ["address", "street_address", "property_address", "location"],
            "city": ["city", "municipality", "jurisdiction"],
            "zip_code": ["zip", "zipcode", "postal_code", "zip_code"],
            "square_footage": ["sqft", "square_feet", "building_area", "floor_area", "total_area"],
            "lot_size": ["lot_area", "parcel_area", "land_area", "lot_square_feet"],
            "year_built": ["year_built", "construction_year", "built_year", "year_constructed"],
            "assessed_value": ["assessed_value", "assessment", "tax_value", "appraised_value"],
            "market_value": ["market_value", "fair_market_value", "current_value", "estimated_value"],
            "property_type": ["type", "property_type", "use_code", "property_class", "classification"]
        }
        
        # Match discovered fields to standard fields
        discovered_fields = data_schema.get("fields", [])
        
        for standard_field, patterns in field_patterns.items():
            for discovered_field in discovered_fields:
                discovered_lower = discovered_field.lower()
                for pattern in patterns:
                    if pattern in discovered_lower or discovered_lower in pattern:
                        mappings[discovered_field] = standard_field
                        break
        
        return mappings
    
    async def _calculate_data_quality_score(self, data_schema: Dict[str, Any]) -> float:
        """Calculate data quality score based on schema analysis"""
        score = 0.0
        max_score = 1.0
        
        # Field completeness (40% of score)
        expected_fields = ["property_id", "address", "city", "square_footage", "assessed_value"]
        discovered_fields = data_schema.get("fields", [])
        
        field_coverage = len([f for f in expected_fields if any(ef.lower() in f.lower() for ef in discovered_fields)]) / len(expected_fields)
        score += field_coverage * 0.4
        
        # Data availability (30% of score)
        has_sample_data = len(data_schema.get("sample_data", {})) > 0
        score += (0.3 if has_sample_data else 0.0)
        
        # Schema structure (30% of score)
        has_structured_data = len(discovered_fields) >= 5
        score += (0.3 if has_structured_data else 0.0)
        
        return min(score, max_score)
    
    def _generate_recommendations(self, documentation: APIDocumentation, health_status: str) -> List[str]:
        """Generate recommendations for API integration"""
        recommendations = []
        
        if health_status == "inactive":
            recommendations.append("API appears to be inactive - verify URL and connectivity")
        elif health_status == "rate_limited":
            recommendations.append("API is rate limited - implement proper rate limiting strategy")
        
        if not documentation.endpoints:
            recommendations.append("No endpoints discovered - manual endpoint configuration may be needed")
        
        if documentation.authentication.get("required", False):
            recommendations.append("Authentication required - configure API credentials")
        
        if len(documentation.endpoints) > 10:
            recommendations.append("Many endpoints discovered - prioritize based on data needs")
        
        if not documentation.rate_limits.get("detected", False):
            recommendations.append("Rate limits not detected - implement conservative rate limiting")
        
        return recommendations
    
    async def _save_documentation(self, documentation: APIDocumentation) -> None:
        """Save API documentation to file"""
        import os
        from pathlib import Path
        
        # Get absolute path for API documentation
        docs_path = Path(settings.API_DOCUMENTATION_PATH)
        if not docs_path.is_absolute():
            # If relative path, make it relative to the current working directory
            docs_path = Path.cwd() / docs_path
        
        # Create directory if it doesn't exist
        docs_path.mkdir(parents=True, exist_ok=True)
        
        file_path = docs_path / f"{documentation.api_name}.yaml"
        
        # Convert to dict and save as YAML
        doc_dict = documentation.dict()
        doc_dict["last_updated"] = documentation.last_updated.isoformat()
        
        with open(file_path, "w") as f:
            yaml.dump(doc_dict, f, default_flow_style=False)
        
        logger.info("API documentation saved", api_name=documentation.api_name, file_path=str(file_path))
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose() 