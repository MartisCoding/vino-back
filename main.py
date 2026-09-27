import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI
from loguru import logger

from src.config import Config
from src.resources import Resources, create_resources
from src.resources.queue_listener_factory import (
    CVInferenceQueueListener,
    OCRInferenceQueueListener,
    QueueListenerFactory,
)
from src.routes.recognition import RecognitionController
from src.services.factories import ServiceFactory


class Application:
    def __init__(self, config: Config):
        self.config = config

        self.resources: Resources | None = None
        self.service_factory: ServiceFactory | None = None
        self.listener_factory: QueueListenerFactory | None = None  # type: ignore
        self.app: FastAPI | None = None

    def logger_setup(self) -> None:
        logger.remove()

        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:"
            "<cyan>{function}</cyan>:"
            "<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

        logger.add(
            sys.stderr,
            level=self.config.logging.level,
            format=log_format,
            serialize=self.config.logging.serialize,
            backtrace=True,
            diagnose=False,
        )

        if self.config.logging.file:
            log_path = Path(self.config.logging.logs_directory) / self.config.logging.file
            log_path.parent.mkdir(parents=True, exist_ok=True)

            logger.add(
                log_path,
                level=self.config.logging.level,
                format=log_format,
                serialize=self.config.logging.serialize,
                backtrace=True,
                diagnose=False,
                encoding="utf-8",
            )
        logger.info("Logger setup complete with level: {}", self.config.logging.level)

    async def prelude(self) -> None:
        logger.info("Starting application prelude routine")
        logger.debug("Creating resources")
        self.resources = create_resources(self.config)

        logger.debug("Connecting to RabbitMQ")
        try:
            await self.resources.rabbitmq_client.connect()
        except Exception as e:
            logger.error("Failed to connect to RabbitMQ: {}", e, exc_info=True)
            raise

        logger.debug("RabbitMQ connection established")

        logger.debug("Checking PostgreSQL database connection")
        await self.resources.connection_manager.test_connection()
        logger.debug("PostgreSQL database connection successful")

        logger.debug("Creating service factory")
        self.service_factory = ServiceFactory(self.resources, self.config)
        logger.debug("Service factory created")

        logger.debug("Creating Listener factory")
        self.listener_factory = QueueListenerFactory(self.resources)
        logger.debug("Listener factory created")

        logger.debug("Creating CV Inference Queue Listener")
        cv_listener = CVInferenceQueueListener(self.resources, self.service_factory)
        self.listener_factory.create_queue_listener(
            listener_name=self.config.rabbitmq.inference_worker.worker_name,
            queue_name=self.config.rabbitmq.inference_worker.consume_queue,
            handler=cv_listener.handler,
        )
        logger.debug("CV Inference Queue Listener created and started")

        logger.debug("Creating OCR Inference Queue Listener")
        ocr_listener = OCRInferenceQueueListener(self.resources, self.service_factory)
        self.listener_factory.create_queue_listener(
            listener_name=self.config.rabbitmq.inference_ocr_worker.worker_name,
            queue_name=self.config.rabbitmq.inference_ocr_worker.consume_queue,
            handler=ocr_listener.handler,
        )
        logger.debug("OCR Inference Queue Listener created and started")

        logger.info("Application prelude routine completed successfully")

    def create_app(self):
        if not self.resources or not self.service_factory:
            raise RuntimeError("Resources and ServiceFactory must be initialized before creating FastAPI app")

        if not self.listener_factory:
            raise RuntimeError("ListenerFactory must be initialized before creating FastAPI app")

        if self.app:
            raise RuntimeError("FastAPI app has already been created")

        logger.debug("Creating FastAPI application")
        recognition_router = APIRouter(prefix="/recognition", tags=["Recognition"])
        recognition_controller = RecognitionController(
            router=recognition_router,
            resources=self.resources,
            service_factory=self.service_factory
        )

        logger.debug("Including recognition router in the FastAPI application")

        self.app = FastAPI(
            title=self.config.app_name, 
            version=self.config.app_version,
            lifespan=self.lifespan,
            debug=self.config.fastapi.debug,
            )
        self.app.include_router(recognition_router)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        logger.info("Starting application lifespan context")
        await self.prelude()

        try:
            yield
        finally:
            logger.info("Shutting down application lifespan context")
            if self.listener_factory:
                await self.listener_factory.stop_all_listeners()
            if self.resources:
                await self.resources.connection_manager.close()
                await self.resources.rabbitmq_client.close()
            logger.info("Application shutdown complete")

    def run(self):
        self.logger_setup()
        self.create_app()

        if not self.app:
            raise RuntimeError("Error creating FastAPI app")

        logger.info("Starting FastAPI application with Uvicorn")
        uvicorn.run(
            self.app,
            host=self.config.fastapi.host,
            port=self.config.fastapi.port,
            log_level=self.config.logging.level.lower(),
        )

if __name__ == "__main__":
    config = Config()
    app = Application(config)
    app.run()
