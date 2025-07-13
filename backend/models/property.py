"""
Property model definition
"""

from sqlalchemy import Column, String, Float, Integer, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin
import enum

class PropertyType(str, enum.Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    LAND = "land"

class ZoningType(str, enum.Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    MIXED = "mixed"
    AGRICULTURAL = "agricultural"

class Property(Base, TimestampMixin):
    """Property model representing real estate properties"""
    __tablename__ = 'properties'

    id = Column(String, primary_key=True)
    property_type = Column(Enum(PropertyType), nullable=False)
    zoning_type = Column(Enum(ZoningType), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    raw_data = Column(JSON, nullable=True)

    # Relationships
    address_id = Column(Integer, ForeignKey('addresses.id'), nullable=False)
    address = relationship("Address", back_populates="property")
    
    metrics_id = Column(Integer, ForeignKey('property_metrics.id'), nullable=False)
    metrics = relationship("PropertyMetrics", back_populates="property")
    
    financials_id = Column(Integer, ForeignKey('property_financials.id'), nullable=False)
    financials = relationship("PropertyFinancials", back_populates="property")

    def __repr__(self):
        return f"<Property(id={self.id}, type={self.property_type})>" 