"""
Base model configuration for SQLAlchemy
"""

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, DateTime, func
from datetime import datetime

class Base(DeclarativeBase):
    """Base class for all models"""
    pass

class TimestampMixin:
    """Mixin for adding created_at and updated_at timestamps"""
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False) 