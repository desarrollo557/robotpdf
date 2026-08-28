"""
SQLAlchemy Base Model and Session Configuration
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import DateTime, func
from typing import Optional, Any
from datetime import datetime

from ..core.settings import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class BaseModel(DeclarativeBase):
    """
    Base model with common fields and configurations
    """
    
    __abstract__ = True
    
    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name in snake_case"""
        return cls.__name__.lower() + "s"
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db_session():
    """
    Dependency for FastAPI to get a database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize database tables
    """
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
        logger.info("Database tables initialized")


async def close_db():
    """
    Close database connections
    """
    await engine.dispose()
    logger.info("Database connections closed")
