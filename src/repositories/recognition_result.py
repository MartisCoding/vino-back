from collections.abc import Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.tables import RecognitionResult


class RecognitionResultRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def _require_result(self, result_id: str) -> RecognitionResult:
        result = await self._session.get(RecognitionResult, result_id)
        if result is None:
            raise ValueError(f"Recognition result with id {result_id} not found")
        return result

    async def create_empty(
            self,
            task_id: str, # The ID of the recognition task associated with this result
    ) -> RecognitionResult:
        logger.debug("Creating empty recognition result for task_id={}", task_id)
        result = RecognitionResult(
            id=task_id,
            status="accepting_results",
        )
        self._session.add(result)
        await self._session.flush()
        logger.info("Empty recognition result created result_id={}", result.id)
        return result

    async def get_by_id(self, result_id: str) -> RecognitionResult | None:
        logger.debug("Fetching recognition result by id={}", result_id)
        result = await self._session.get(RecognitionResult, result_id)
        logger.debug("Recognition result by id={} found={}", result_id, result is not None)
        return result

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[RecognitionResult]:
        logger.debug("Listing recognition results limit={} offset={}", limit, offset)
        stmt = select(RecognitionResult).offset(offset).limit(limit)
        rows = await self._session.scalars(stmt)
        results = rows.all()
        logger.debug("Listed recognition results count={}", len(results))
        return results

    async def delete(self, result: RecognitionResult) -> None:
        logger.debug("Deleting recognition result id={}", result.id)
        await self._session.delete(result)
        await self._session.flush()
        logger.info("Recognition result deleted id={}", result.id)

    async def update_status(self, result_id: str, new_status: str) -> RecognitionResult:
        result = await self._require_result(result_id)
        logger.debug("Updating recognition result id={} status={} -> {}", result_id, result.status, new_status)
        result.status = new_status
        await self._session.flush()
        logger.info("Recognition result updated id={} status={}", result.id, result.status)
        return result

    async def update(self, result_id: str, **changes: object) -> RecognitionResult:
        result = await self._require_result(result_id)
        logger.debug("Updating recognition result id={} fields={}", result_id, list(changes.keys()))
        for field, value in changes.items():
            if hasattr(result, field):
                setattr(result, field, value)
            else:
                logger.warning("Skipping unknown recognition result field update: {}", field)
        await self._session.flush()
        logger.info("Recognition result updated id={}", result.id)
        return result
    