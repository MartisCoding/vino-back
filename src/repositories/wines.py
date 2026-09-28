from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.tables import Wine


class WineRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def inflate(self, catalog: list[dict[str, Any]]):
        """Inflate the database with a list of wines"""
        import json
        records = [
            (
                wine["slug"],
                wine["wine_id"],
                wine["name"],
                wine["producer"],
                wine["region"],
                wine["style"],
                wine["color"],
                wine["grapes"],
                wine.get("year"),
                wine.get("alcohol_percent"),
                wine.get("image_url"),
                json.dumps(wine.get("aliases", [])),
                wine["search_text"],
            )
            for wine in catalog
        ]

        connection = await self._session.connection()
        raw_conn = await connection.get_raw_connection()
        driver_connection = raw_conn.driver_connection
        await driver_connection.copy_records_to_table(
            "wines",
            records=records,
            columns=[
                "slug",
                "wine_id",
                "name",
                "producer",
                "region",
                "style",
                "color",
                "grapes",
                "year",
                "alcohol_percent",
                "image_url",
                "aliases",
                "search_text",
            ],
        )

    async def create(
        self,
        slug: str,
        wine_id: str,
        name: str,
        producer: str,
        region: str,
        style: list[str],
        color: str,
        grapes: list[str],
        year: int | None = None,
        alcohol_percent: float | None = None,
        image_url: str | None = None,
        aliases: list[dict] = [],
        search_text: str = "",
    ) -> Wine:
        logger.debug("Creating wine with slug={}", slug)
        
        wine = Wine(
            slug=slug,
            wine_id=wine_id,
            name=name,
            producer=producer,
            region=region,
            style=style,
            color=color,
            grapes=grapes,
            year=year,
            alcohol_percent=alcohol_percent,
            image_url=image_url,
            aliases=aliases,
            search_text=search_text,
        )
        self._session.add(wine)
        await self._session.flush()
        logger.info("Wine created id={} slug={}", wine.id, wine.slug)
        return wine

    async def get_by_id(self, wine_id: int) -> Wine | None:
        logger.debug("Fetching wine by id={}", wine_id)
        wine = await self._session.get(Wine, wine_id)
        logger.debug("Wine by id={} found={}", wine_id, wine is not None)
        return wine

    async def get_by_slug(self, slug: str) -> Wine | None:
        logger.debug("Fetching wine by slug={}", slug)
        stmt = select(Wine).where(Wine.slug == slug)
        wine = await self._session.scalar(stmt)
        logger.debug("Wine by slug={} found={}", slug, wine is not None)
        return wine

    async def get_by_identifier(
        self,
        wine_id: int | None = None,
        wine_slug: str | None = None,
    ) -> Wine | None:
        if wine_id is None and wine_slug is None:
            logger.error("Wine identifier lookup failed: both identifiers are missing")
            raise ValueError("At least one wine identifier must be provided.")

        filters = []
        if wine_id is not None:
            filters.append(Wine.id == wine_id)
        if wine_slug is not None:
            filters.append(Wine.slug == wine_slug)

        stmt = select(Wine).where(*filters)
        wine = await self._session.scalar(stmt)
        logger.debug(
            "Wine by identifiers id={} slug={} found={}",
            wine_id,
            wine_slug,
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

    async def find_similar_by_slug(self, slug: str, limit: int = 3) -> Sequence[Wine]:
        logger.debug("Finding similar wines for slug={} limit={}", slug, limit)
        stmt = select(Wine)
        wines = (await self._session.scalars(stmt)).all()
        ranked = sorted(
            wines,
            key=lambda wine: SequenceMatcher(None, slug, wine.slug).ratio(),
            reverse=True,
        )
        similar = [wine for wine in ranked if wine.slug != slug][:limit]
        logger.debug("Found similar wines count={} for slug={}", len(similar), slug)
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
        logger.debug("Deleting wine id={} slug={}", wine.id, wine.slug)
        await self._session.delete(wine)
        await self._session.flush()
        logger.info("Wine deleted id={} slug={}", wine.id, wine.slug)
