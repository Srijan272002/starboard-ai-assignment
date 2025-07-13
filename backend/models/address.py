"""
Address model definition
"""

from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class Address(Base, TimestampMixin):
    """Address model for property locations"""
    __tablename__ = 'addresses'

    id = Column(Integer, primary_key=True)
    street = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String(2), nullable=False)
    postal_code = Column(String(10), nullable=False)
    country = Column(String(2), nullable=False, default='US')

    # Relationship
    property = relationship("Property", back_populates="address", uselist=False)

    def __repr__(self):
        return f"<Address(id={self.id}, street={self.street}, city={self.city})>" 