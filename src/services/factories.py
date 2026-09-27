from sqlalchemy.ext.asyncio import AsyncSession

from repositories.recognition_result import RecognitionResultRepository
from services.recognition_service import RecognitionService
from src.config import Config
from src.repositories import (
    RecognitionTaskRepository,
    UploadedImageRepository,
    WineImageRepository,
    WineRepository,
)
from src.resources import Resources
from src.services.image_service import ImageService


class ServiceFactory:
    def __init__(self, resources: Resources, config: Config):
        self.resources = resources
        self.config = config

    def image_service(self, session: AsyncSession) -> ImageService:
        return ImageService(
            minio_client=self.resources.minio_client,
            image_bucket=self.config.minio.image_bucket,
            uploaded_image_repository=UploadedImageRepository(session),
            wine_image_repository=WineImageRepository(session),
            wine_repository=WineRepository(session),
        )

    def recognition_service(self, session: AsyncSession) -> RecognitionService:
        return RecognitionService(
            task_repository=RecognitionTaskRepository(session),
            result_repository=RecognitionResultRepository(session),
            wine_parser=self.resources.parser,
            wine_repository=WineRepository(session),
            rabbitmq_client=self.resources.rabbitmq_client,
            workers_configs={"inference": self.config.rabbitmq.inference_worker, "ocr_inference": self.config.rabbitmq.inference_ocr_worker},
            resolver=self.resources.resolver,
        )
