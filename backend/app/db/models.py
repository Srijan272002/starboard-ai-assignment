from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from datetime import datetime
from app.db.base import Base

class Property(Base):
    """Industrial property model."""
    __tablename__ = "properties"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic property information
    property_id = Column(String, unique=True, index=True)  # External property ID
    county = Column(String, index=True)  # Cook, Dallas, or LA
    address = Column(String)
    city = Column(String, index=True)
    state = Column(String, index=True)
    zip_code = Column(String, index=True)
    
    # Property details
    property_type = Column(String, index=True)  # Industrial, Warehouse, etc.
    zoning = Column(String, index=True)  # M1, M2, I-1, I-2, etc.
    square_footage = Column(Float)  # Building square footage
    lot_size = Column(Float)  # Lot size in square feet
    year_built = Column(Integer)
    
    # Location data
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Financial data
    assessed_value = Column(Float)
    market_value = Column(Float)
    tax_amount = Column(Float)
    
    # Property features (stored as JSON for flexibility)
    features = Column(JSON)  # Loading docks, crane capacity, ceiling height, etc.
    
    # Data quality and processing
    data_quality_score = Column(Float)  # Score from 0-1 indicating data completeness
    confidence_score = Column(Float)  # Confidence in property classification
    processing_status = Column(String, default="pending")  # pending, processed, error
    
    # Images and media
    image_url = Column(String)  # Primary property image URL
    additional_images = Column(JSON)  # Array of additional image URLs
    
    # Raw data from source APIs (for debugging and reprocessing)
    raw_data = Column(JSON)
    
    # Metadata
    source_api = Column(String)  # Which county API this came from
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Version tracking
    current_version_id = Column(Integer, index=True)
    is_latest = Column(Boolean, default=True, index=True)
    
    # Relationships
    versions = relationship("PropertyVersion", back_populates="property", cascade="all, delete-orphan")
    backups = relationship("PropertyBackup", back_populates="property", cascade="all, delete-orphan")
    archives = relationship("PropertyArchive", back_populates="property", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Property(id={self.id}, address='{self.address}', county='{self.county}')>"

class PropertyVersion(Base):
    """Model for tracking property data versions."""
    __tablename__ = "property_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), index=True)
    version_number = Column(Integer, index=True)
    
    # Snapshot of property data at this version
    data = Column(JSON)
    
    # Change tracking
    changes = Column(JSON)  # What changed from previous version
    change_type = Column(String)  # "update", "correction", "assessment", etc.
    change_reason = Column(String)  # Why the change was made
    
    # Metadata
    created_by = Column(String)  # User or system that created this version
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    property = relationship("Property", back_populates="versions")
    
    def __repr__(self):
        return f"<PropertyVersion(property_id={self.property_id}, version={self.version_number})>"

class PropertyBackup(Base):
    """Model for property data backups."""
    __tablename__ = "property_backups"
    
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), index=True)
    
    # Backup details
    backup_type = Column(String)  # "daily", "weekly", "monthly"
    data = Column(JSON)  # Full property data backup
    storage_path = Column(String)  # Path to external backup storage if applicable
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))  # When this backup expires
    
    # Relationships
    property = relationship("Property", back_populates="backups")
    
    def __repr__(self):
        return f"<PropertyBackup(property_id={self.property_id}, type='{self.backup_type}')>"

class PropertyArchive(Base):
    """Model for archived property data (historical/inactive properties)."""
    __tablename__ = "property_archives"
    
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), index=True)
    
    # Archive details
    archive_reason = Column(String)  # Why it was archived
    data = Column(JSON)  # Full property data at time of archiving
    is_compressed = Column(Boolean, default=True)
    
    # Metadata
    archived_at = Column(DateTime(timezone=True), server_default=func.now())
    retention_period_days = Column(Integer, default=3650)  # Default 10 years
    
    # Relationships
    property = relationship("Property", back_populates="archives")
    
    def __repr__(self):
        return f"<PropertyArchive(property_id={self.property_id}, archived_at={self.archived_at})>"

class DataUpdateLog(Base):
    """Model for tracking data updates and synchronization."""
    __tablename__ = "data_update_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Update details
    update_type = Column(String)  # "full", "incremental", "correction"
    source = Column(String)  # Data source
    records_processed = Column(Integer)
    records_updated = Column(Integer)
    records_failed = Column(Integer)
    
    # Status tracking
    status = Column(String)  # "pending", "in_progress", "completed", "failed"
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    
    # Error tracking
    error_message = Column(Text)
    error_details = Column(JSON)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<DataUpdateLog(type='{self.update_type}', status='{self.status}', records={self.records_processed})>"

class BackupJob(Base):
    """Model for tracking backup jobs."""
    __tablename__ = "backup_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Backup details
    backup_type = Column(String)  # "full", "incremental", "differential"
    target_path = Column(String)  # Where the backup is stored
    file_name = Column(String)
    file_size_bytes = Column(Integer)
    is_compressed = Column(Boolean, default=True)
    is_encrypted = Column(Boolean, default=False)
    
    # Status tracking
    status = Column(String)  # "pending", "in_progress", "completed", "failed"
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    
    # Error tracking
    error_message = Column(Text)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<BackupJob(type='{self.backup_type}', status='{self.status}')>"

class PropertyComparable(Base):
    """Model for storing property comparables and similarity scores."""
    __tablename__ = "property_comparables"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Reference property and comparable property
    property_id = Column(Integer, index=True)  # Foreign key to Property
    comparable_property_id = Column(Integer, index=True)  # Foreign key to Property
    
    # Similarity scores (0-1 scale)
    overall_similarity_score = Column(Float)
    size_similarity = Column(Float)
    location_similarity = Column(Float)
    type_similarity = Column(Float)
    age_similarity = Column(Float)
    features_similarity = Column(Float)
    
    # Distance between properties (miles)
    distance_miles = Column(Float)
    
    # Confidence in the comparison
    confidence_score = Column(Float)
    
    # Analysis metadata
    analysis_version = Column(String)  # Version of comparison algorithm used
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<PropertyComparable(property={self.property_id}, comparable={self.comparable_property_id}, score={self.overall_similarity_score})>"

class APILog(Base):
    """Model for tracking API calls and performance."""
    __tablename__ = "api_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # API call details
    county = Column(String, index=True)
    endpoint = Column(String)
    request_method = Column(String)
    request_params = Column(JSON)
    
    # Response details
    response_status = Column(Integer)
    response_time_ms = Column(Integer)
    response_size_bytes = Column(Integer)
    
    # Error tracking
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    error_type = Column(String)
    
    # Rate limiting
    rate_limit_remaining = Column(Integer)
    rate_limit_reset = Column(DateTime(timezone=True))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<APILog(county='{self.county}', success={self.success}, created_at={self.created_at})>"


# Pydantic models for API requests and responses
class PropertySearchParams(BaseModel):
    """Parameters for property search"""
    property_type: Optional[str] = None
    min_size: Optional[float] = None
    max_size: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    limit: Optional[int] = 50
    offset: Optional[int] = 0


class StandardizedProperty(BaseModel):
    """Standardized property data model"""
    property_id: str
    source: str
    address: str
    city: str
    state: str
    zip_code: str
    county: str
    property_type: str
    square_feet: Optional[float] = None
    price: Optional[float] = None
    price_per_sqft: Optional[float] = None
    year_built: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: str = ""
    listing_url: Optional[str] = None
    contact_info: Optional[str] = None
    image_url: Optional[str] = None
    additional_images: Optional[List[str]] = None
    last_updated: datetime
    raw_data: Dict[str, Any] = {}
    data_quality_score: float = 0.0
    version: Optional[int] = None

    class Config:
        from_attributes = True


class PropertyVersionInfo(BaseModel):
    """Information about a property version"""
    version_number: int
    created_at: datetime
    created_by: str
    change_type: str
    change_reason: str
    changes: Dict[str, Any] = {}

    class Config:
        from_attributes = True


class BackupInfo(BaseModel):
    """Information about a backup"""
    id: int
    backup_type: str
    created_at: datetime
    expires_at: datetime
    file_size_bytes: Optional[int] = None
    storage_path: Optional[str] = None

    class Config:
        from_attributes = True


class APIResponse(BaseModel):
    """Standard API response model"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    count: Optional[int] = None
    total: Optional[int] = None

    class Config:
        from_attributes = True 