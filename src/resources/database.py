from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from loguru import logger

from src.config import DatabaseConfig


class ConnectionManager:

    def __init__(self, config: DatabaseConfig):
        logger.debug(
            "Initializing database connection manager for host={} port={} database={}",
            config.host,
            config.port,
            config.database,
        )
        self._engine: AsyncEngine = create_async_engine(
            config.url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Database connection manager initialized")

    async def close(self) -> None:
        logger.debug("Closing database engine")
        await self._engine.dispose()
        logger.info("Database engine closed")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[AsyncSession, None]:
        logger.debug("Acquiring database session")
        async with self._session_factory() as session:
            try:
                yield session
            finally:
                logger.debug("Database session released")