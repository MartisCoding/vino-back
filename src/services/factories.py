from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.repositories import RecognitionTaskRepository, UploadedImageRepository, WineImageRepository, WineRepository
from src.resources import RabbitMQClient
from src.services.image_service import ImageService
from src.services.recognition_task_service import RecognitionTaskService
from src.services.wine_parser_service import WineParserService


class ServiceFactory:
    def __init__(self, config: Config, minio_client: Minio, rabbitmq_client: RabbitMQClient):
        self._config = config
        self._minio_client = minio_client
        self._rabbitmq_client = rabbitmq_client

    def create_image_service(self, session: AsyncSession) -> ImageService:
        wine_repository = WineRepository(session)
        uploaded_image_repository = UploadedImageRepository(session)
        wine_image_repository = WineImageRepository(session)
        return ImageService(
            minio_client=self._minio_client,
            image_bucket=self._config.minio.image_bucket,
            uploaded_image_repository=uploaded_image_repository,
            wine_image_repository=wine_image_repository,
            wine_repository=wine_repository,
        )

    def create_recognition_task_service(self, session: AsyncSession) -> RecognitionTaskService:
        wine_repository = WineRepository(session)
        task_repository = RecognitionTaskRepository(session)
        return RecognitionTaskService(
            task_repository=task_repository,
            wine_repository=wine_repository,
            rabbitmq_client=self._rabbitmq_client,
            queue_name=self._config.rabbitmq.recognition_queue,
        )

    def create_wine_repository(self, session: AsyncSession) -> WineRepository:
        return WineRepository(session)

    def create_recognition_task_repository(self, session: AsyncSession) -> RecognitionTaskRepository:
        return RecognitionTaskRepository(session)

    def create_wine_parser_service(self, session: AsyncSession) -> WineParserService:
        return WineParserService(
            wine_repository=self.create_wine_repository(session),
            config=self._config.parser,
        )
