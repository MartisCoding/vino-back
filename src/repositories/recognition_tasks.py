from datetime import datetime
from typing import Literal, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.tables import RecognitionTask

TaskStatus = Literal["pending", "processing", "completed", "failed"]


class RecognitionTaskRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, uploaded_image_id: int, status: TaskStatus = "pending") -> RecognitionTask:
        logger.debug("Creating recognition task for uploaded_image_id={} status={}", uploaded_image_id, status)
        task = RecognitionTask(uploaded_image_id=uploaded_image_id, status=status)
        self._session.add(task)
        await self._session.flush()
        logger.info("Recognition task created id={} uploaded_image_id={}", task.id, task.uploaded_image_id)
        return task

    async def get_by_id(self, task_id: str) -> RecognitionTask | None:
        logger.debug("Fetching recognition task by id={}", task_id)
        task = await self._session.get(RecognitionTask, task_id)
        logger.debug("Recognition task by id={} found={}", task_id, task is not None)
        return task

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        status: TaskStatus | None = None,
    ) -> Sequence[RecognitionTask]:
        logger.debug("Listing recognition tasks limit={} offset={} status={}", limit, offset, status)
        stmt = select(RecognitionTask).offset(offset).limit(limit)
        if status is not None:
            stmt = stmt.where(RecognitionTask.status == status)
        rows = await self._session.scalars(stmt)
        tasks = rows.all()
        logger.debug("Listed recognition tasks count={}", len(tasks))
        return tasks

    async def update_status(
        self,
        task: RecognitionTask,
        status: TaskStatus,
        *,
        detected_wine_id: int | None = None,
        detected_wine_external_id: str | None = None,
        error: str | None = None,
        finished_at: datetime | None = None,
    ) -> RecognitionTask:
        logger.debug(
            "Updating recognition task id={} status={} detected_wine_id={} detected_wine_external_id={}",
            task.id,
            status,
            detected_wine_id,
            detected_wine_external_id,
        )
        task.status = status
        task.detected_wine_id = detected_wine_id
        task.detected_wine_external_id = detected_wine_external_id
        task.error = error
        task.finished_at = finished_at
        await self._session.flush()
        logger.info("Recognition task updated id={} status={}", task.id, task.status)
        return task

    async def delete(self, task: RecognitionTask) -> None:
        logger.debug("Deleting recognition task id={}", task.id)
        await self._session.delete(task)
        await self._session.flush()
        logger.info("Recognition task deleted id={}", task.id)
