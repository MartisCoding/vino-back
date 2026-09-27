from minio import Minio
from dataclasses import dataclass

from src.resources.database import ConnectionManager
from src.resources.minio import create_minio_client
from src.resources.parser import WineParser
from src.resources.rabbitmq import RabbitMQClient, create_rabbitmq_client
from src.resources.resolver import RecognitionResolver

__all__ = [
    "ConnectionManager",
    "RabbitMQClient",
    "create_minio_client",
    "create_rabbitmq_client",
]

@dataclass
class Resources:
    connection_manager: ConnectionManager
    rabbitmq_client: RabbitMQClient
    minio_client: Minio
    parser: WineParser
    resolver: RecognitionResolver

def create_resources(config) -> Resources:
    connection_manager = ConnectionManager(config.database)
    rabbitmq_client = create_rabbitmq_client(config.rabbitmq)
    minio_client = create_minio_client(config.minio)
    parser = WineParser(config.parser)
    resolver = RecognitionResolver()
    return Resources(
        connection_manager=connection_manager,
        rabbitmq_client=rabbitmq_client,
        minio_client=minio_client,
        parser=parser,
        resolver=resolver
    )

from src.resources.queue_listener_factory import QueueListenerFactory, CVInferenceQueueListener, OCRInferenceQueueListener
