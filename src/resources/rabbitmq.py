import json
from typing import Any

from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractIncomingMessage
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
        await self._channel.declare_queue(self._config.task_publish_queue, durable=True)
        logger.info("RabbitMQ connected and queue declared: {}", self._config.task_publish_queue)
        await self._channel.declare_queue(self._config.task_result_queue, durable=True)
        logger.info("RabbitMQ connected and queue declared: {}", self._config.task_result_queue)

    async def close(self) -> None:
        logger.debug("Closing RabbitMQ client")
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        logger.info("RabbitMQ client closed")

    async def publish_task(self, payload: dict[str, Any]) -> None:
        if self._channel is None or self._channel.is_closed:
            logger.error("RabbitMQ publish failed: channel is not initialized")
            raise RuntimeError("RabbitMQ channel is not initialized. Call connect() first.")

        logger.debug(
            "Publishing message to queue={} task_id={}",
            self._config.task_publish_queue,
            payload.get("task_id"),
        )
        message = aio_pika.Message(
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self._channel.default_exchange.publish(message, routing_key=self._config.task_publish_queue)
        logger.info("Message published to queue={} task_id={}", self._config.task_publish_queue, payload.get("task_id"))
        
    async def consume_result(
        self,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if self._channel is None or self._channel.is_closed:
            logger.error("RabbitMQ consume failed: channel is not initialized")
            raise RuntimeError(
                "RabbitMQ channel is not initialized. Call connect() first."
            )

        queue = await self._channel.get_queue(self._config.task_result_queue)

        logger.info(
            "Started consuming queue={}",
            self._config.task_result_queue,
        )

        async def on_message(
            message: AbstractIncomingMessage,
        ) -> None:
            async with message.process():
                try:
                    payload = json.loads(
                        message.body.decode("utf-8")
                    )

                    logger.debug(
                        "Received message queue={} payload={}",
                        self._config.task_result_queue,
                        payload,
                    )

                    await callback(payload)

                except Exception:
                    logger.exception(
                        "Failed to process message queue={}",
                        self._config.task_result_queue,
                    )
                    raise

        await queue.consume(on_message)

def create_rabbitmq_client(config: RabbitMQConfig) -> RabbitMQClient:
    logger.debug("Creating RabbitMQ client for host={} port={}", config.host, config.port)
    return RabbitMQClient(config)
