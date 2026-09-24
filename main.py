import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from loguru import logger

from src.config import Config
from src.resources import ConnectionManager, create_minio_client, create_rabbitmq_client
from src.routes import recognition_router
from src.services import ServiceFactory
from src.consumer.recognition_result_consumer import RecognitionResultConsumer
config = Config()

def init_logger():
    logger.remove()
    
    if config.logging.log_path:
        logger.add(
            config.logging.log_path,
            level=config.logging.level,
            serialize=config.logging.serialize
        )
    else:
        logger.add(
            sink=lambda msg: print(msg, end=""),
            level=config.logging.level,
            serialize=config.logging.serialize,
        )


@asynccontextmanager
async def startup_shutdown_indicate(app: FastAPI):
    logger.info("Starting application")

    connection_manager = ConnectionManager(config.database)
    logger.debug("Conn_man initialized with config: {}", config.database)
    minio_client = create_minio_client(config.minio)
    logger.debug("MinIO client created with config: {}", config.minio)
    rabbitmq_client = create_rabbitmq_client(config.rabbitmq)
    logger.debug("RabbitMQ client created with config: {}", config.rabbitmq)
    await rabbitmq_client.connect()
    service_factory = ServiceFactory(
        config=config,
        minio_client=minio_client,
        rabbitmq_client=rabbitmq_client,
    )
    logger.debug("ServiceFactory created with config: {}", config)
    
    consumer = RecognitionResultConsumer(
        connection_manager=connection_manager,
        service_factory=service_factory,
    )
    
    consumer_task = asyncio.create_task(
        rabbitmq_client.consume_result(consumer.handle)
    )

    app.state.config = config
    app.state.connection_manager = connection_manager
    app.state.minio_client = minio_client
    app.state.rabbitmq_client = rabbitmq_client
    app.state.service_factory = service_factory

    logger.info("Application resources initialized")
    
    yield
    logger.info("Stopping application")
    
    consumer_task.cancel()

    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    await rabbitmq_client.close()
    await connection_manager.close()
    

def create_app() -> FastAPI:
    app = FastAPI(
        title=config.fastapi.title,
        debug=config.fastapi.debug,
        lifespan=startup_shutdown_indicate
    )
    app.include_router(recognition_router)
    return app

def main() -> None:
    init_logger()
    
    app = create_app()
    
    logger.debug("Launching app with configuration: {}", config)
    
    uvicorn.run(
        app,
        host=config.fastapi.host,
        port=config.fastapi.port
    )
    
if __name__ == "__main__":
    main()