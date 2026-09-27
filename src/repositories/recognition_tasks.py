from collections.abc import Sequence
from typing import Literal

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.tables import RecognitionTask

TaskStatus = Literal["pending", "processing", "completed", "failed"]


class RecognitionTaskRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, uploaded_image_id: int) -> RecognitionTask:
        logger.debug("Creating recognition task for uploaded_image_id={}", uploaded_image_id)
        task = RecognitionTask(uploaded_image_id=uploaded_image_id)
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
    ) -> Sequence[RecognitionTask]:
        logger.debug("Listing recognition tasks limit={} offset={}", limit, offset)
        stmt = select(RecognitionTask).offset(offset).limit(limit)
        rows = await self._session.scalars(stmt)
        tasks = rows.all()
        logger.debug("Listed recognition tasks count={}", len(tasks))
        return tasks

    async def delete(self, task: RecognitionTask) -> None:
        logger.debug("Deleting recognition task id={}", task.id)
        await self._session.delete(task)
        await self._session.flush()
        logger.info("Recognition task deleted id={}", task.id)
