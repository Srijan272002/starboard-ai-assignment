"""
Application configuration
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings"""
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Starboard Property Analysis"
    
    # CORS Settings
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Database Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "starboard"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "starboard_db"
    DATABASE_URL: Optional[str] = None
    
    # Redis Settings
    REDIS_URL: str = ""
    RATE_LIMIT_REDIS_URL: str = ""  # Will use REDIS_URL if not set
    
    # County API URLs
    COOK_COUNTY_API_URL: str = "https://datacatalog.cook...resource/93st-4bxh.json"
    DALLAS_COUNTY_API_URL: str = "https://docs.google.com/...stgovk/edit?usp=sharing"
    LA_COUNTY_API_URL: str = "https://docs.google.com/...mOo-Mg/edit?usp=sharing"
    
    # County API Keys
    COOK_COUNTY_API_KEY: str = ""
    DALLAS_COUNTY_API_KEY: str = ""
    LA_COUNTY_API_KEY: str = ""
    API_KEY_HEADER: str = "X-API-KEY"
    
    # API Data Settings
    REAL_API_REQUIRED: bool = True  # If True, will fail if real API data cannot be fetched
    ALLOW_MOCK_DATA: bool = False   # If True, allows mock data as fallback in development
    
    # JWT Settings
    JWT_SECRET_KEY: str = "starboard_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    
    # API Rate Limits (requests per minute)
    DEFAULT_RATE_LIMIT: int = 100
    COOK_COUNTY_RATE_LIMIT: int = 60
    DALLAS_COUNTY_RATE_LIMIT: int = 60
    LA_COUNTY_RATE_LIMIT: int = 60
    
    # API Timeouts (seconds)
    REQUEST_TIMEOUT: float = 30.0
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    MAX_CONCURRENT_REQUESTS: int = 10  # Maximum number of concurrent requests
    
    # Batch Processing
    MAX_BATCH_SIZE: int = 100
    BATCH_TIMEOUT: float = 30.0
    
    # Health Monitoring
    HEALTH_CHECK_INTERVAL: int = 300  # 5 minutes
    
    # API Documentation
    API_DOCUMENTATION_PATH: str = "./api_docs"
    
    # Field Mapping
    FIELD_MAPPING_CONFIG_PATH: str = "./config/field_mappings.yaml"
    FUZZY_MATCH_THRESHOLD: float = 0.8  # 80% similarity for fuzzy matching
    
    # Data Storage Settings
    BACKUP_DIRECTORY: str = "./data/backups"
    ARCHIVE_DIRECTORY: str = "./data/archives"
    ARCHIVE_RETENTION_DAYS: int = 3650  # 10 years default retention
    
    # Backup Settings
    DAILY_BACKUP_RETENTION_DAYS: int = 7
    WEEKLY_BACKUP_RETENTION_DAYS: int = 30
    MONTHLY_BACKUP_RETENTION_DAYS: int = 365
    
    # External APIs
    GEOCODING_API_KEY: str = ""
    MARKET_DATA_API_KEY: str = ""
    
    # Environment
    ENVIRONMENT: str = "development"  # development, staging, production
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def get_database_url(self) -> str:
        """
        Construct database URL from components if not explicitly provided
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        
        # Default to SQLite for development if PostgreSQL settings not provided
        if not all([self.POSTGRES_SERVER, self.POSTGRES_USER, self.POSTGRES_DB]):
            return "sqlite:///./starboard.db"
        
        # Construct PostgreSQL URL
        password_str = f":{self.POSTGRES_PASSWORD}" if self.POSTGRES_PASSWORD else ""
        return f"postgresql://{self.POSTGRES_USER}{password_str}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
        
    def get_cors_origins(self) -> List[str]:
        """Return the list of allowed CORS origins"""
        if self.BACKEND_CORS_ORIGINS:
            # Parse comma-separated string of origins
            origins = [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]
            # Use explicit list if provided, otherwise use parsed origins
            return origins if origins else self.CORS_ORIGINS
        return self.CORS_ORIGINS


# Create global settings instance
settings = Settings()


# Helper function to get absolute path
def get_absolute_path(relative_path: str) -> Path:
    """Convert relative path to absolute path"""
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return Path.cwd() / path 