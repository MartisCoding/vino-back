import hashlib
from io import BytesIO
from mimetypes import guess_extension
from uuid import uuid4

from loguru import logger
from minio import Minio

from src.repositories import (
    UploadedImageRepository,
    WineImageRepository,
    WineRepository,
)
from src.tables import UploadedImage, WineImage


class ImageService:
    def __init__(
        self,
        minio_client: Minio,
        image_bucket: str,
        uploaded_image_repository: UploadedImageRepository,
        wine_image_repository: WineImageRepository,
        wine_repository: WineRepository,
    ):
        self._minio_client = minio_client
        self._image_bucket = image_bucket
        self._uploaded_image_repository = uploaded_image_repository
        self._wine_image_repository = wine_image_repository
        self._wine_repository = wine_repository

    def _ensure_bucket(self) -> None:
        logger.debug("Ensuring MinIO bucket exists: {}", self._image_bucket)
        if not self._minio_client.bucket_exists(self._image_bucket):
            logger.info("MinIO bucket does not exist, creating: {}", self._image_bucket)
            self._minio_client.make_bucket(self._image_bucket)
        else:
            logger.debug("MinIO bucket already exists: {}", self._image_bucket)

    @staticmethod
    def _hash_bytes(image_bytes: bytes) -> str:
        return hashlib.sha256(image_bytes).hexdigest()

    @staticmethod
    def _file_extension(content_type: str) -> str:
        extension = guess_extension(content_type, strict=False)
        return extension or ".bin"

    def _put_object(self, object_key: str, image_bytes: bytes, content_type: str) -> None:
        logger.debug(
            "Uploading object to MinIO bucket={} object_key={} size={} content_type={}",
            self._image_bucket,
            object_key,
            len(image_bytes),
            content_type,
        )
        self._minio_client.put_object(
            bucket_name=self._image_bucket,
            object_name=object_key,
            data=BytesIO(image_bytes),
            length=len(image_bytes),
            content_type=content_type,
        )
        logger.info("Object uploaded to MinIO bucket={} object_key={}", self._image_bucket, object_key)

    async def upload_client_image(
        self,
        image_bytes: bytes,
        content_type: str,
        extension: str | None = None,
    ) -> UploadedImage:
        logger.debug(
            "Uploading client image size={} content_type={}",
            len(image_bytes),
            content_type,
        )

        self._ensure_bucket()

        extension = extension or self._file_extension(content_type)

        object_key = f"client/{uuid4()}{extension}"

        sha256_hash = self._hash_bytes(image_bytes)

        self._put_object(
            object_key=object_key,
            image_bytes=image_bytes,
            content_type=content_type,
        )

        image = await self._uploaded_image_repository.create(
            object_key=object_key,
            content_type=content_type,
            size=len(image_bytes),
            sha256_hash=sha256_hash,
        )

        logger.info(
            "Client image persisted id={} object_key={}",
            image.id,
            image.object_key,
        )

        return image

    async def upload_reference_image(
        self,
        image_bytes: bytes,
        content_type: str,
        *,
        wine_id: int | None = None,
        wine_external_id: str | None = None,
    ) -> WineImage:
        logger.debug(
            "Uploading reference image size={} content_type={} wine_id={} wine_external_id={}",
            len(image_bytes),
            content_type,
            wine_id,
            wine_external_id,
        )
        wine = await self._wine_repository.get_by_identifier(wine_id, wine_external_id)
        if wine is None:
            logger.warning(
                "Reference image upload failed: wine not found by wine_id={} wine_external_id={}",
                wine_id,
                wine_external_id,
            )
            raise ValueError("Wine was not found by provided identifiers.")

        self._ensure_bucket()
        object_key = f"reference/{wine.slug}/{uuid4()}{self._file_extension(content_type)}"
        sha256_hash = self._hash_bytes(image_bytes)

        self._put_object(object_key=object_key, image_bytes=image_bytes, content_type=content_type)

        wine_image = await self._wine_image_repository.create(
            wine_id=wine.id,
            wine_external_id=wine.slug,
            object_key=object_key,
            content_type=content_type,
            size=len(image_bytes),
            sha256_hash=sha256_hash,
        )
        logger.info(
            "Reference image persisted id={} object_key={} wine_id={} wine_external_id={}",
            wine_image.id,
            wine_image.object_key,
            wine_image.wine_id,
            wine_image.wine_external_id,
        )
        return wine_image

    async def delete_client_image(self, image_id: int) -> None:
        logger.debug("Deleting client image id={}", image_id)
        image = await self._uploaded_image_repository.get_by_id(image_id)
        if image is None:
            logger.warning("Client image delete failed: image id={} not found", image_id)
            raise ValueError(f"Uploaded image with id={image_id} does not exist.")
        self._remove_object(image.object_key)
        await self._uploaded_image_repository.delete(image)
        logger.info("Client image deleted id={} object_key={}", image.id, image.object_key)

    async def delete_reference_image(self, image_id: int) -> None:
        logger.debug("Deleting reference image id={}", image_id)
        image = await self._wine_image_repository.get_by_id(image_id)
        if image is None:
            logger.warning("Reference image delete failed: image id={} not found", image_id)
            raise ValueError(f"Reference image with id={image_id} does not exist.")
        self._remove_object(image.object_key)
        await self._wine_image_repository.delete(image)
        logger.info("Reference image deleted id={} object_key={}", image.id, image.object_key)

    def _remove_object(self, object_key: str) -> None:
        logger.debug("Removing object from MinIO bucket={} object_key={}", self._image_bucket, object_key)
        self._minio_client.remove_object(bucket_name=self._image_bucket, object_name=object_key)
        logger.info("Object removed from MinIO bucket={} object_key={}", self._image_bucket, object_key)
