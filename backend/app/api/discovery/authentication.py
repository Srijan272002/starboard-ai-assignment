"""
Authentication Handler - Manages various API authentication methods
"""

import base64
import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Union
from enum import Enum
import structlog
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class AuthType(str, Enum):
    """Supported authentication types"""
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    OAUTH2 = "oauth2"
    JWT = "jwt"


class AuthConfig(BaseModel):
    """Authentication configuration"""
    auth_type: AuthType
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"
    api_key_param: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    token_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scope: Optional[str] = None
    extra_headers: Dict[str, str] = {}
    extra_params: Dict[str, str] = {}


class AuthenticationHandler:
    """Handles authentication for various API types"""
    
    def __init__(self):
        self.cached_tokens: Dict[str, Dict[str, Any]] = {}
    
    def create_auth_config(
        self,
        auth_type: AuthType,
        county: str,
        **kwargs
    ) -> AuthConfig:
        """
        Create authentication configuration for a county API
        
        Args:
            auth_type: Type of authentication
            county: County name (cook, dallas, la)
            **kwargs: Additional authentication parameters
            
        Returns:
            AuthConfig object
        """
        config = AuthConfig(auth_type=auth_type, **kwargs)
        
        # Set county-specific defaults
        if county.lower() == "cook":
            config.api_key = settings.COOK_COUNTY_API_KEY
        elif county.lower() == "dallas":
            config.api_key = settings.DALLAS_COUNTY_API_KEY
        elif county.lower() == "la":
            config.api_key = settings.LA_COUNTY_API_KEY
            
        logger.info("Created auth config", county=county, auth_type=auth_type.value)
        return config
    
    async def get_auth_headers(
        self,
        config: AuthConfig,
        county: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Get authentication headers for API requests
        
        Args:
            config: Authentication configuration
            county: County name for token caching
            
        Returns:
            Dictionary of headers to include in requests
        """
        headers = {}
        
        try:
            if config.auth_type == AuthType.NONE:
                pass  # No authentication needed
                
            elif config.auth_type == AuthType.API_KEY:
                if config.api_key:
                    headers[config.api_key_header] = config.api_key
                else:
                    raise StarboardException("API key not configured")
                    
            elif config.auth_type == AuthType.BEARER_TOKEN:
                if config.token:
                    headers["Authorization"] = f"Bearer {config.token}"
                else:
                    raise StarboardException("Bearer token not configured")
                    
            elif config.auth_type == AuthType.BASIC_AUTH:
                if config.username and config.password:
                    credentials = base64.b64encode(
                        f"{config.username}:{config.password}".encode()
                    ).decode()
                    headers["Authorization"] = f"Basic {credentials}"
                else:
                    raise StarboardException("Basic auth credentials not configured")
                    
            elif config.auth_type == AuthType.OAUTH2:
                token = await self._get_oauth2_token(config, county)
                headers["Authorization"] = f"Bearer {token}"
                
            elif config.auth_type == AuthType.JWT:
                token = self._generate_jwt_token(config)
                headers["Authorization"] = f"Bearer {token}"
            
            # Add extra headers
            headers.update(config.extra_headers)
            
            logger.debug("Generated auth headers", auth_type=config.auth_type.value)
            return headers
            
        except Exception as e:
            logger.error("Failed to generate auth headers", 
                        auth_type=config.auth_type.value, 
                        error=str(e))
            raise StarboardException(f"Authentication failed: {str(e)}")
    
    async def get_auth_params(
        self,
        config: AuthConfig,
        county: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Get authentication parameters for API requests
        
        Args:
            config: Authentication configuration
            county: County name for token caching
            
        Returns:
            Dictionary of parameters to include in requests
        """
        params = {}
        
        try:
            if config.auth_type == AuthType.API_KEY and config.api_key_param:
                if config.api_key:
                    params[config.api_key_param] = config.api_key
                else:
                    raise StarboardException("API key not configured")
            
            # Add extra params
            params.update(config.extra_params)
            
            logger.debug("Generated auth params", auth_type=config.auth_type.value)
            return params
            
        except Exception as e:
            logger.error("Failed to generate auth params", 
                        auth_type=config.auth_type.value, 
                        error=str(e))
            raise StarboardException(f"Authentication failed: {str(e)}")
    
    async def _get_oauth2_token(
        self,
        config: AuthConfig,
        county: Optional[str] = None
    ) -> str:
        """Get OAuth2 access token"""
        import httpx
        
        cache_key = f"oauth2_token_{county or 'default'}"
        
        # Check cache
        if cache_key in self.cached_tokens:
            token_data = self.cached_tokens[cache_key]
            if datetime.utcnow() < token_data["expires_at"]:
                return token_data["token"]
        
        # Get new token
        if not config.token_url:
            raise StarboardException("OAuth2 token URL not configured")
        
        data = {
            "grant_type": "client_credentials",
            "client_id": config.client_id,
            "client_secret": config.client_secret
        }
        
        if config.scope:
            data["scope"] = config.scope
        
        async with httpx.AsyncClient() as client:
            response = await client.post(config.token_url, data=data)
            response.raise_for_status()
            
            token_response = response.json()
            access_token = token_response["access_token"]
            expires_in = token_response.get("expires_in", 3600)
            
            # Cache token
            self.cached_tokens[cache_key] = {
                "token": access_token,
                "expires_at": datetime.utcnow() + timedelta(seconds=expires_in - 60)  # 60s buffer
            }
            
            logger.info("OAuth2 token obtained", county=county)
            return access_token
    
    def _generate_jwt_token(self, config: AuthConfig) -> str:
        """Generate JWT token"""
        if not settings.JWT_SECRET_KEY:
            raise StarboardException("JWT secret key not configured")
        
        payload = {
            "iss": settings.PROJECT_NAME,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        }
        
        # Add any additional claims from config
        if hasattr(config, 'jwt_claims'):
            payload.update(config.jwt_claims)
        
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        
        logger.info("JWT token generated")
        return token
    
    async def validate_authentication(
        self,
        config: AuthConfig,
        test_url: str
    ) -> bool:
        """
        Validate authentication configuration by making a test request
        
        Args:
            config: Authentication configuration
            test_url: URL to test authentication against
            
        Returns:
            True if authentication is valid, False otherwise
        """
        import httpx
        
        try:
            headers = await self.get_auth_headers(config)
            params = await self.get_auth_params(config)
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(test_url, headers=headers, params=params)
                
                # Consider 200, 201, 202 as success
                # 401 means auth failed, 403 means insufficient permissions
                if response.status_code in [200, 201, 202]:
                    logger.info("Authentication validation successful", 
                               auth_type=config.auth_type.value)
                    return True
                elif response.status_code in [401, 403]:
                    logger.warning("Authentication validation failed", 
                                  auth_type=config.auth_type.value,
                                  status_code=response.status_code)
                    return False
                else:
                    # Other status codes might indicate the endpoint is working
                    # but with different expected behavior
                    logger.info("Authentication validation inconclusive", 
                               auth_type=config.auth_type.value,
                               status_code=response.status_code)
                    return True
                    
        except Exception as e:
            logger.error("Authentication validation error", 
                        auth_type=config.auth_type.value,
                        error=str(e))
            return False
    
    def get_county_auth_config(self, county: str) -> AuthConfig:
        """
        Get default authentication configuration for a county
        
        Args:
            county: County name (cook, dallas, la)
            
        Returns:
            Default AuthConfig for the county
        """
        county_lower = county.lower()
        
        if county_lower == "cook":
            # Cook County typically uses API keys
            return self.create_auth_config(
                auth_type=AuthType.API_KEY,
                county=county,
                api_key_header="X-App-Token",
                api_key_param="$$app_token"
            )
            
        elif county_lower == "dallas":
            # Dallas County configuration - update based on actual requirements
            return self.create_auth_config(
                auth_type=AuthType.API_KEY,
                county=county,
                api_key_header="X-API-Key"
            )
            
        elif county_lower == "la":
            # LA County configuration - update based on actual requirements
            return self.create_auth_config(
                auth_type=AuthType.API_KEY,
                county=county,
                api_key_header="X-API-Key"
            )
            
        else:
            # Default to no authentication
            return self.create_auth_config(
                auth_type=AuthType.NONE,
                county=county
            )
    
    def clear_token_cache(self, county: Optional[str] = None):
        """Clear cached tokens"""
        if county:
            cache_key = f"oauth2_token_{county}"
            self.cached_tokens.pop(cache_key, None)
            logger.info("Cleared token cache", county=county)
        else:
            self.cached_tokens.clear()
            logger.info("Cleared all token cache") 