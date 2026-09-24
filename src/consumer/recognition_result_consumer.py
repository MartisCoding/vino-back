
from typing import Any

from src.services.factories import ServiceFactory
from src.resources.database import ConnectionManager


class RecognitionResultConsumer:
    def __init__(
        self,
        connection_manager: ConnectionManager,
        service_factory: ServiceFactory,
    ):
        self._connection_manager = connection_manager
        self._service_factory = service_factory

    async def handle(self, payload: dict[str, Any]) -> None:
        async with self._connection_manager.acquire() as session:
            service = self._service_factory.create_recognition_task_service(
                session
            )

            await service.confirm_task(
                task_id=payload["task_id"],
                status=payload["status"],
                detected_wine_id=payload.get("detected_wine_id"),
                detected_wine_external_id=payload.get("detected_wine_external_id"),
                error=payload.get("error"),
            )

            await session.commit()