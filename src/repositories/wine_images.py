from collections.abc import Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.tables import WineImage


class WineImageRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        wine_id: int,
        wine_external_id: str,
        object_key: str,
        content_type: str,
        size: int,
        sha256_hash: str,
    ) -> WineImage:
        logger.debug(
            "Creating wine image record wine_id={} external_id={} object_key={}",
            wine_id,
            wine_external_id,
            object_key,
        )
        wine_image = WineImage(
            wine_id=wine_id,
            wine_external_id=wine_external_id,
            object_key=object_key,
            content_type=content_type,
            size=size,
            sha256_hash=sha256_hash,
        )
        self._session.add(wine_image)
        await self._session.flush()
        logger.info("Wine image created id={} object_key={}", wine_image.id, wine_image.object_key)
        return wine_image

    async def get_by_id(self, image_id: int) -> WineImage | None:
        logger.debug("Fetching wine image by id={}", image_id)
        image = await self._session.get(WineImage, image_id)
        logger.debug("Wine image by id={} found={}", image_id, image is not None)
        return image

    async def get_by_object_key(self, object_key: str) -> WineImage | None:
        logger.debug("Fetching wine image by object_key={}", object_key)
        stmt = select(WineImage).where(WineImage.object_key == object_key)
        image = await self._session.scalar(stmt)
        logger.debug("Wine image by object_key={} found={}", object_key, image is not None)
        return image

    async def list_by_wine_id(self, wine_id: int) -> Sequence[WineImage]:
        logger.debug("Listing wine images by wine_id={}", wine_id)
        stmt = select(WineImage).where(WineImage.wine_id == wine_id)
        rows = await self._session.scalars(stmt)
        images = rows.all()
        logger.debug("Wine images by wine_id={} count={}", wine_id, len(images))
        return images

    async def list_by_wine_external_id(self, wine_external_id: str) -> Sequence[WineImage]:
        logger.debug("Listing wine images by wine_external_id={}", wine_external_id)
        stmt = select(WineImage).where(WineImage.wine_external_id == wine_external_id)
        rows = await self._session.scalars(stmt)
        images = rows.all()
        logger.debug("Wine images by wine_external_id={} count={}", wine_external_id, len(images))
        return images

    async def list(self, limit: int = 100, offset: int = 0) -> Sequence[WineImage]:
        logger.debug("Listing wine images limit={} offset={}", limit, offset)
        stmt = select(WineImage).offset(offset).limit(limit)
        rows = await self._session.scalars(stmt)
        images = rows.all()
        logger.debug("Listed wine images count={}", len(images))
        return images

    async def update(self, wine_image: WineImage, **changes: object) -> WineImage:
        logger.debug("Updating wine image id={} fields={}", wine_image.id, list(changes.keys()))
        for field, value in changes.items():
            if hasattr(wine_image, field):
                setattr(wine_image, field, value)
            else:
                logger.warning("Skipping unknown wine image field update: {}", field)
        await self._session.flush()
        logger.info("Wine image updated id={}", wine_image.id)
        return wine_image

    async def delete(self, wine_image: WineImage) -> None:
        logger.debug("Deleting wine image id={} object_key={}", wine_image.id, wine_image.object_key)
        await self._session.delete(wine_image)
        await self._session.flush()
        logger.info("Wine image deleted id={} object_key={}", wine_image.id, wine_image.object_key)
