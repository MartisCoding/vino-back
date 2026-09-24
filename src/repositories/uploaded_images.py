from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.tables import UploadedImage


class UploadedImageRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        object_key: str,
        content_type: str,
        size: int,
        sha256_hash: str,
    ) -> UploadedImage:
        logger.debug("Creating uploaded image record object_key={} size={}", object_key, size)
        image = UploadedImage(
            object_key=object_key,
            content_type=content_type,
            size=size,
            sha256_hash=sha256_hash,
        )
        self._session.add(image)
        await self._session.flush()
        logger.info("Uploaded image created id={} object_key={}", image.id, image.object_key)
        return image

    async def get_by_id(self, image_id: int) -> UploadedImage | None:
        logger.debug("Fetching uploaded image by id={}", image_id)
        image = await self._session.get(UploadedImage, image_id)
        logger.debug("Uploaded image by id={} found={}", image_id, image is not None)
        return image

    async def get_by_object_key(self, object_key: str) -> UploadedImage | None:
        logger.debug("Fetching uploaded image by object_key={}", object_key)
        stmt = select(UploadedImage).where(UploadedImage.object_key == object_key)
        image = await self._session.scalar(stmt)
        logger.debug("Uploaded image by object_key={} found={}", object_key, image is not None)
        return image

    async def list(self, limit: int = 100, offset: int = 0) -> Sequence[UploadedImage]:
        logger.debug("Listing uploaded images limit={} offset={}", limit, offset)
        stmt = select(UploadedImage).offset(offset).limit(limit)
        rows = await self._session.scalars(stmt)
        images = rows.all()
        logger.debug("Listed uploaded images count={}", len(images))
        return images

    async def update(self, image: UploadedImage, **changes: object) -> UploadedImage:
        logger.debug("Updating uploaded image id={} fields={}", image.id, list(changes.keys()))
        for field, value in changes.items():
            if hasattr(image, field):
                setattr(image, field, value)
            else:
                logger.warning("Skipping unknown uploaded image field update: {}", field)
        await self._session.flush()
        logger.info("Uploaded image updated id={}", image.id)
        return image

    async def delete(self, image: UploadedImage) -> None:
        logger.debug("Deleting uploaded image id={} object_key={}", image.id, image.object_key)
        await self._session.delete(image)
        await self._session.flush()
        logger.info("Uploaded image deleted id={} object_key={}", image.id, image.object_key)
