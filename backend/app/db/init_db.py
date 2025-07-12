"""
Database initialization script
"""

import logging
from sqlalchemy.exc import SQLAlchemyError
from app.db.base import Base, engine
from app.core.logging import get_logger

logger = get_logger(__name__)

def init_db() -> None:
    """Initialize the database by creating all tables"""
    try:
        logger.info("Creating database tables")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except SQLAlchemyError as e:
        logger.error("Failed to initialize database", error=str(e))
        raise 