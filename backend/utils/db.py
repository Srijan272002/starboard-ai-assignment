"""
Database management utilities
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging
from ..config.settings import get_settings
from ..models.base import Base

logger = logging.getLogger(__name__)
settings = get_settings()

def get_engine(database_url: str = None):
    """Create SQLAlchemy async engine with the given database URL"""
    if database_url is None:
        database_url = settings.DATABASE_URL
        
    # Convert standard PostgreSQL URL to async format
    if database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
    
    return create_async_engine(
        database_url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800
    )

async def init_db(database_url: str = None) -> None:
    """Initialize database with all models"""
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")

def get_session_maker(database_url: str = None) -> async_sessionmaker[AsyncSession]:
    """Create an async session maker"""
    engine = get_engine(database_url)
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session with automatic cleanup"""
    session_maker = get_session_maker()
    session = session_maker()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error: {str(e)}")
        raise
    finally:
        await session.close()

async def cleanup_db(database_url: str = None) -> None:
    """Drop all tables - use with caution!"""
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("Database cleaned up successfully") 