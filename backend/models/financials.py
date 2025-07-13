"""
Property financials model definition
"""

from sqlalchemy import Column, Integer, Float, Date, JSON
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class PropertyFinancials(Base, TimestampMixin):
    """PropertyFinancials model for storing financial data related to properties"""
    __tablename__ = 'property_financials'

    id = Column(Integer, primary_key=True)
    list_price = Column(Float, nullable=True)
    sale_price = Column(Float, nullable=True)
    last_sale_date = Column(Date, nullable=True)
    estimated_value = Column(Float, nullable=True)
    annual_tax = Column(Float, nullable=True)
    monthly_hoa = Column(Float, nullable=True)
    rental_estimate = Column(Float, nullable=True)
    additional_fees = Column(JSON, nullable=True)

    # Relationship
    property = relationship("Property", back_populates="financials", uselist=False)

    def __repr__(self):
        return f"<PropertyFinancials(id={self.id}, estimated_value={self.estimated_value})>" 