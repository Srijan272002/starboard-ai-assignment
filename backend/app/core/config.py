from typing import List, Optional, Dict, Any
from pydantic import validator
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Starboard AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: Optional[str] = None
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "starboard"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "starboard_db"
    
    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict) -> str:
        if isinstance(v, str):
            return v
        return f"postgresql://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}@{values.get('POSTGRES_SERVER')}/{values.get('POSTGRES_DB')}"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # API Configuration
    COOK_COUNTY_API_URL: str = "https://datacatalog.cookcountyil.gov/resource/"
    DALLAS_COUNTY_API_URL: str = "https://www.dallascounty.org/departments/tax/"
    LA_COUNTY_API_URL: str = "https://portal.assessor.lacounty.gov/"
    
    # API Discovery Configuration
    API_DISCOVERY_ENABLED: bool = True
    API_HEALTH_CHECK_INTERVAL: int = 300  # seconds
    API_DOCUMENTATION_PATH: str = "api_docs"
    AUTO_API_CATALOGING: bool = True
    
    # County-specific API settings
    COOK_COUNTY_API_KEY: Optional[str] = None
    COOK_COUNTY_RATE_LIMIT: int = 1000  # requests per hour
    COOK_COUNTY_BATCH_SIZE: int = 100
    
    DALLAS_COUNTY_API_KEY: Optional[str] = None
    DALLAS_COUNTY_RATE_LIMIT: int = 500  # requests per hour
    DALLAS_COUNTY_BATCH_SIZE: int = 50
    
    LA_COUNTY_API_KEY: Optional[str] = None
    LA_COUNTY_RATE_LIMIT: int = 2000  # requests per hour
    LA_COUNTY_BATCH_SIZE: int = 200
    
    # Rate Limiting
    DEFAULT_RATE_LIMIT: int = 100  # requests per minute
    RATE_LIMIT_STRATEGY: str = "sliding_window"  # sliding_window, fixed_window, token_bucket
    RATE_LIMIT_REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    
    # Authentication
    API_KEY_HEADER: str = "X-API-Key"
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    
    # Field Standardization
    FIELD_MAPPING_CONFIG_PATH: str = "config/field_mappings.yaml"
    FUZZY_MATCH_THRESHOLD: float = 0.8
    DATA_QUALITY_THRESHOLD: float = 0.7
    ENABLE_FIELD_NORMALIZATION: bool = True
    ENABLE_TYPE_VALIDATION: bool = True
    
    # Data Processing
    MAX_CONCURRENT_REQUESTS: int = 10
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_FACTOR: float = 1.5
    
    # Batch Processing
    BATCH_PROCESSING_ENABLED: bool = True
    BATCH_SIZE: int = 100
    BATCH_TIMEOUT: int = 300
    
    # Data Quality
    ENABLE_DATA_QUALITY_CHECKS: bool = True
    MISSING_DATA_THRESHOLD: float = 0.5  # Allow up to 50% missing data
    DATA_COMPLETENESS_SCORE_WEIGHT: float = 0.4
    DATA_ACCURACY_SCORE_WEIGHT: float = 0.6
    
    # Logging
    LOG_LEVEL: str = "INFO"
    ENABLE_API_LOGGING: bool = True
    LOG_API_REQUESTS: bool = True
    LOG_API_RESPONSES: bool = False  # Set to True for debugging
    
    # Cache Configuration
    ENABLE_CACHING: bool = True
    CACHE_TTL: int = 3600  # 1 hour
    REDIS_URL: Optional[str] = "redis://localhost:6379/1"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings() 