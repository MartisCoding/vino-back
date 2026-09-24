import json
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractConnection
from loguru import logger

from src.config import RabbitMQConfig


class RabbitMQClient:
    def __init__(self, config: RabbitMQConfig):
        self._config = config
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None

    async def connect(self) -> None:
        if self._connection and not self._connection.is_closed:
            logger.debug("RabbitMQ connection already open")
            return

        logger.debug(
            "Connecting to RabbitMQ host={} port={} vhost={}",
            self._config.host,
            self._config.port,
            self._config.virtual_host,
        )
        self._connection = await aio_pika.connect_robust(self._config.url)
        self._channel = await self._connection.channel()
        await self._channel.declare_queue(self._config.recognition_queue, durable=True)
        logger.info("RabbitMQ connected and queue declared: {}", self._config.recognition_queue)

    async def close(self) -> None:
        logger.debug("Closing RabbitMQ client")
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        logger.info("RabbitMQ client closed")

    async def publish_json(self, queue_name: str, payload: dict[str, Any]) -> None:
        if self._channel is None or self._channel.is_closed:
            logger.error("RabbitMQ publish failed: channel is not initialized")
            raise RuntimeError("RabbitMQ channel is not initialized. Call connect() first.")

        logger.debug(
            "Publishing message to queue={} task_id={}",
            queue_name,
            payload.get("task_id"),
        )
        message = aio_pika.Message(
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self._channel.default_exchange.publish(message, routing_key=queue_name)
        logger.info("Message published to queue={} task_id={}", queue_name, payload.get("task_id"))


def create_rabbitmq_client(config: RabbitMQConfig) -> RabbitMQClient:
    logger.debug("Creating RabbitMQ client for host={} port={}", config.host, config.port)
    return RabbitMQClient(config)
