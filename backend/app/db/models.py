from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.sql import func
from typing import Optional, Any, Dict
from pydantic import BaseModel
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
    
    # Raw data from source APIs (for debugging and reprocessing)
    raw_data = Column(JSON)
    
    # Metadata
    source_api = Column(String)  # Which county API this came from
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Property(id={self.id}, address='{self.address}', county='{self.county}')>"

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
    last_updated: datetime
    raw_data: Dict[str, Any] = {}
    data_quality_score: float = 0.0

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