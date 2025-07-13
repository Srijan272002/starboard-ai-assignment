"""
Property metrics model definition
"""

from sqlalchemy import Column, Integer, Float, JSON
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class PropertyMetrics(Base, TimestampMixin):
    """PropertyMetrics model for storing property measurements and characteristics"""
    __tablename__ = 'property_metrics'

    id = Column(Integer, primary_key=True)
    square_footage = Column(Float, nullable=False)
    lot_size = Column(Float, nullable=False)
    year_built = Column(Integer, nullable=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Float, nullable=True)
    parking_spaces = Column(Integer, nullable=True)
    additional_features = Column(JSON, nullable=True)

    # Relationship
    property = relationship("Property", back_populates="metrics", uselist=False)

    def __repr__(self):
        return f"<PropertyMetrics(id={self.id}, square_footage={self.square_footage})>" 