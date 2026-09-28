import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from src.resources import Resources
from src.services.factories import ServiceFactory


class QueueListenerFactory:
    def __init__(self, resources: Resources):
        self._resources = resources

        self.tasks: dict[str, asyncio.Task[None]] = {}

    def create_queue_listener(
        self,
        listener_name: str,
        queue_name: str,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        async def listener():
            logger.info(
                "Starting queue listener for queue: {}",
                queue_name,
            )

            try:
                await self._resources.rabbitmq_client.consume_result(
                    queue_name,
                    handler,
                )

                await asyncio.Future()
            except Exception:
                logger.exception(
                    "Error occurred while consuming queue={}",
                    queue_name,
                )

        task = asyncio.create_task(listener())
        self.tasks[listener_name] = task

    async def stop_queue_listener(self, listener_name: str) -> None:
        task = self.tasks.get(listener_name)
        if task:
            task.cancel()
            logger.info("Stopped queue listener: {}", listener_name)
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("Queue listener task cancelled: {}", listener_name)
        else:
            logger.warning("No queue listener found with name: {}", listener_name)

    async def stop_all_listeners(self) -> None:
        for listener_name, task in self.tasks.items():
            task.cancel()
            logger.info("Stopping queue listener: {}", listener_name)
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("Queue listener task cancelled: {}", listener_name)


# --- Listener classes goes here.

class CVInferenceQueueListener:
    def __init__(self, resources: Resources, service_factory: ServiceFactory):
        self._resources = resources
        self._service_factory = service_factory

    async def handler(self, message: dict[str, Any]) -> None:
        logger.debug("CVInferenceQueueListener received message: {}", message)
        async with self._resources.connection_manager.acquire() as session:
            recognition_service = self._service_factory.recognition_service(session)
            try:
                await recognition_service.accept_cv_result(
                    task_id=message["task_id"],
                    cv_response=message["result"],
                )
            except Exception as e:
                logger.error("Error processing CV inference result for task_id={}, error={}, message={}", message.get("task_id"), e, message, exc_info=True)
                raise

class OCRInferenceQueueListener:
    def __init__(self, resources: Resources, service_factory: ServiceFactory):
        self._resources = resources
        self._service_factory = service_factory

    async def handler(self, message: dict[str, Any]) -> None:
        logger.debug("OCRInferenceQueueListener received message: {}", message)
        async with self._resources.connection_manager.acquire() as session:
            recognition_service = self._service_factory.recognition_service(session)
            try:
                await recognition_service.accept_ocr_result(
                    task_id=message["task_id"],
                    ocr_response=message["result"],
                )
            except Exception as e:
                logger.error("Error processing OCR inference result for task_id={}, error={}, message={}", message.get("task_id"), e, message, exc_info=True)
                raise