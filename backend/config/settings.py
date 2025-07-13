from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Dict, Optional
import logging
from pathlib import Path

# Set up debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Get the absolute path to the .env file
ENV_FILE = Path(__file__).parent.parent / '.env'

class Settings(BaseSettings):
    """
    Application settings and environment variables
    """
    # API Keys
    ATTOMDATA_API_KEY: str
    OPENAI_API_KEY: str

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/starboard"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # API Settings
    API_HOST: str = "localhost"
    API_PORT: int = 8000

    # Rate Limits
    MAX_REQUESTS_PER_MINUTE: int = 60
    MAX_CONCURRENT_REQUESTS: int = 10

    # Feature Flags
    ENABLE_CACHE: bool = True
    DEBUG_MODE: bool = False

    # Attomdata API Configuration
    ATTOMDATA_BASE_URL: str = "https://api.attomdata.com/v2"
    ATTOMDATA_RATE_LIMIT: int = 5  # requests per second
    ATTOMDATA_TIMEOUT: int = 30  # seconds

    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_TIMEOUT: int = 5  # seconds

    # Batch Processing
    BATCH_SIZE: int = 10
    REQUEST_TIMEOUT: float = 30.0

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Backup Configuration
    BACKUP_DIR: str = "backups"
    BACKUP_RETENTION_DAYS: int = 7
    ENABLE_AUTO_BACKUP: bool = True

    # Data Cleanup
    STALE_DATA_THRESHOLD_DAYS: int = 30
    ENABLE_AUTO_CLEANUP: bool = True

    class Config:
        env_file = str(ENV_FILE)
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    """
    logger.debug(f"Current working directory: {Path.cwd()}")
    logger.debug(f"Using .env file at: {ENV_FILE}")
    return Settings() 