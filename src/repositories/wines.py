from difflib import SequenceMatcher
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.tables import Wine


class WineRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        external_id: str,
        name: str,
        country: str,
        region: str,
        winery: str,
        grape: str,
        vintage: str,
        rating: float,
        description: str,
        source_url: str,
    ) -> Wine:
        logger.debug("Creating wine with external_id={}", external_id)
        wine = Wine(
            external_id=external_id,
            name=name,
            country=country,
            region=region,
            winery=winery,
            grape=grape,
            vintage=vintage,
            rating=rating,
            description=description,
            source_url=source_url,
        )
        self._session.add(wine)
        await self._session.flush()
        logger.info("Wine created id={} external_id={}", wine.id, wine.external_id)
        return wine

    async def get_by_id(self, wine_id: int) -> Wine | None:
        logger.debug("Fetching wine by id={}", wine_id)
        wine = await self._session.get(Wine, wine_id)
        logger.debug("Wine by id={} found={}", wine_id, wine is not None)
        return wine

    async def get_by_external_id(self, external_id: str) -> Wine | None:
        logger.debug("Fetching wine by external_id={}", external_id)
        stmt = select(Wine).where(Wine.external_id == external_id)
        wine = await self._session.scalar(stmt)
        logger.debug("Wine by external_id={} found={}", external_id, wine is not None)
        return wine

    async def get_by_identifier(
        self,
        wine_id: int | None = None,
        wine_external_id: str | None = None,
    ) -> Wine | None:
        if wine_id is None and wine_external_id is None:
            logger.error("Wine identifier lookup failed: both identifiers are missing")
            raise ValueError("At least one wine identifier must be provided.")

        filters = []
        if wine_id is not None:
            filters.append(Wine.id == wine_id)
        if wine_external_id is not None:
            filters.append(Wine.external_id == wine_external_id)

        stmt = select(Wine).where(*filters)
        wine = await self._session.scalar(stmt)
        logger.debug(
            "Wine by identifiers id={} external_id={} found={}",
            wine_id,
            wine_external_id,
            wine is not None,
        )
        return wine

    async def list(self, limit: int = 100, offset: int = 0) -> Sequence[Wine]:
        logger.debug("Listing wines limit={} offset={}", limit, offset)
        stmt = select(Wine).offset(offset).limit(limit)
        rows = await self._session.scalars(stmt)
        wines = rows.all()
        logger.debug("Listed wines count={}", len(wines))
        return wines

    async def find_similar_by_external_id(self, external_id: str, limit: int = 3) -> Sequence[Wine]:
        logger.debug("Finding similar wines for external_id={} limit={}", external_id, limit)
        stmt = select(Wine)
        wines = (await self._session.scalars(stmt)).all()
        ranked = sorted(
            wines,
            key=lambda wine: SequenceMatcher(None, external_id, wine.external_id).ratio(),
            reverse=True,
        )
        similar = [wine for wine in ranked if wine.external_id != external_id][:limit]
        logger.debug("Found similar wines count={} for external_id={}", len(similar), external_id)
        return similar

    async def update(self, wine: Wine, **changes: object) -> Wine:
        logger.debug("Updating wine id={} with fields={}", wine.id, list(changes.keys()))
        for field, value in changes.items():
            if hasattr(wine, field):
                setattr(wine, field, value)
            else:
                logger.warning("Skipping unknown wine field update: {}", field)
        await self._session.flush()
        logger.info("Wine updated id={}", wine.id)
        return wine

    async def delete(self, wine: Wine) -> None:
        logger.debug("Deleting wine id={} external_id={}", wine.id, wine.external_id)
        await self._session.delete(wine)
        await self._session.flush()
        logger.info("Wine deleted id={} external_id={}", wine.id, wine.external_id)
