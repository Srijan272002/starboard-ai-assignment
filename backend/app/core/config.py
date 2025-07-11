from typing import List, Optional
from pydantic import BaseSettings, validator
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
    COOK_COUNTY_API_URL: str = ""
    DALLAS_COUNTY_API_URL: str = ""
    LA_COUNTY_API_URL: str = ""
    
    # Rate Limiting
    DEFAULT_RATE_LIMIT: int = 100  # requests per minute
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings() 