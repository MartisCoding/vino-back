from datetime import datetime
from typing import Literal

from loguru import logger
from src.repositories import RecognitionTaskRepository, WineRepository
from src.resources import RabbitMQClient
from src.tables import RecognitionTask

TaskStatus = Literal["pending", "processing", "completed", "failed"]


class RecognitionTaskService:
    def __init__(
        self,
        task_repository: RecognitionTaskRepository,
        wine_repository: WineRepository,
        rabbitmq_client: RabbitMQClient,
    ):
        self._task_repository = task_repository
        self._wine_repository = wine_repository
        self._rabbitmq_client = rabbitmq_client

    async def create_and_send_task(self, uploaded_image_id: int) -> RecognitionTask:
        logger.debug("Creating and sending recognition task for uploaded_image_id={}", uploaded_image_id)
        task = await self._task_repository.create(uploaded_image_id=uploaded_image_id, status="pending")

        await self._rabbitmq_client.publish_task(
            payload={
                "task_id": task.id,
                "uploaded_image_id": task.uploaded_image_id,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
            },
        )
        logger.info("Recognition task sent task_id={} uploaded_image_id={}", task.id, uploaded_image_id)
        return task

    async def mark_processing(self, task_id: str) -> RecognitionTask:
        logger.debug("Marking recognition task as processing task_id={}", task_id)
        task = await self._require_task(task_id)
        updated_task = await self._task_repository.update_status(task, "processing")
        logger.info("Recognition task marked processing task_id={}", task_id)
        return updated_task

    async def confirm_task(
        self,
        task_id: str,
        status: Literal["completed", "failed"],
        *,
        detected_wine_id: int | None = None,
        detected_wine_external_id: str | None = None,
        error: str | None = None,
    ) -> RecognitionTask:
        logger.debug(
            "Confirming recognition task task_id={} status={} detected_wine_id={} detected_wine_external_id={}",
            task_id,
            status,
            detected_wine_id,
            detected_wine_external_id,
        )
        task = await self._require_task(task_id)

        if status == "failed":
            if not error:
                logger.error("Task confirmation failed: missing error for failed status task_id={}", task_id)
                raise ValueError("Error message is required when task status is failed.")
            updated_task = await self._task_repository.update_status(
                task,
                status="failed",
                error=error,
                finished_at=datetime.utcnow(),
            )
            logger.warning("Recognition task marked failed task_id={} error={}", task_id, error)
            return updated_task

        if detected_wine_id is None and detected_wine_external_id is None:
            logger.error("Task confirmation failed: no wine identifiers were provided task_id={}", task_id)
            raise ValueError("Detected wine id or detected wine slug is required for completed tasks.")

        wine = await self._wine_repository.get_by_identifier(detected_wine_id, detected_wine_external_id)
        if wine is not None:
            resolved_wine_id = wine.id
            resolved_wine_external_id = wine.external_id
        elif detected_wine_external_id is not None:
            resolved_wine_id = None
            resolved_wine_external_id = detected_wine_external_id
            logger.warning(
                "Completed task has unknown wine in local DB task_id={} detected_wine_external_id={}",
                task_id,
                detected_wine_external_id,
            )
        else:
            logger.error(
                "Task confirmation failed: detected wine id={} does not exist task_id={}",
                detected_wine_id,
                task_id,
            )
            raise ValueError("Detected wine id was not found.")

        updated_task = await self._task_repository.update_status(
            task,
            status="completed",
            detected_wine_id=resolved_wine_id,
            detected_wine_external_id=resolved_wine_external_id,
            finished_at=datetime.utcnow(),
        )
        logger.info(
            "Recognition task completed task_id={} detected_wine_id={} detected_wine_external_id={}",
            task_id,
            updated_task.detected_wine_id,
            updated_task.detected_wine_external_id,
        )
        return updated_task

    async def _require_task(self, task_id: str) -> RecognitionTask:
        logger.debug("Fetching required recognition task task_id={}", task_id)
        task = await self._task_repository.get_by_id(task_id)
        if task is None:
            logger.warning("Recognition task not found task_id={}", task_id)
            raise ValueError(f"Recognition task with id={task_id} does not exist.")
        return task
