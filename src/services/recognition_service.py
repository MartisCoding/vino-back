from datetime import datetime
from typing import Any, Dict, Literal

from loguru import logger

from models.inference import CVInferenceResponse, OCRInferenceResponse
from src.config.workers_config import WorkersConfig
from src.models.recognition import RecognitionResponse
from src.models.wine import WineDTO
from src.repositories import RecognitionTaskRepository, WineRepository
from src.repositories.recognition_result import RecognitionResultRepository
from src.resources import RabbitMQClient
from src.resources.parser import WineParser
from src.resources.resolver import RecognitionResolver
from src.tables import RecognitionTask, Wine
from tables.recognition_result import RecognitionResult

TaskStatus = Literal["pending", "processing", "completed", "failed"]


class RecognitionService:
    def __init__(
        self,
        task_repository: RecognitionTaskRepository,
        result_repository: RecognitionResultRepository,
        wine_parser: WineParser,
        wine_repository: WineRepository,
        rabbitmq_client: RabbitMQClient,
        workers_configs: dict[str, WorkersConfig],
        resolver: RecognitionResolver,
    ):
        self._task_repository = task_repository
        self._wine_repository = wine_repository
        self._rabbitmq_client = rabbitmq_client
        self._result_repository = result_repository
        self._wine_parser = wine_parser
        self._resolver = resolver

        try:
            self._inference_workers_config = workers_configs["inference"]
        except KeyError:
            raise ValueError(
                "Inference workers configuration is required."
            )

        try:
            self._ocr_inference_workers_config = workers_configs[
                "ocr_inference"
            ]
        except KeyError:
            raise ValueError(
                "OCR inference workers configuration is required."
            )

    async def create_and_send_task(self, uploaded_image_id: int, object_key: str) -> RecognitionTask:
        logger.debug("Creating and sending recognition task for uploaded_image_id={}", uploaded_image_id)
        task = await self._task_repository.create(uploaded_image_id=uploaded_image_id)

        _empty_result = await self._result_repository.create_empty(task_id=task.id)

        payload = {
            "task_id": task.id,
            "object_key": object_key,
        }

        logger.info("Sending recognition task to RabbitMQ queues task_id={} uploaded_image_id={}", task.id, uploaded_image_id)
        
        logger.debug("Publishing task to inference queue={} task_id={}", self._inference_workers_config.publish_queue,)
        await self._rabbitmq_client.publish_task(
            queue_name=self._inference_workers_config.publish_queue,
            payload=payload,
        )

        logger.debug("Publishing task to OCR inference queue={} task_id={}", self._ocr_inference_workers_config.publish_queue,)
        await self._rabbitmq_client.publish_task(
            queue_name=self._ocr_inference_workers_config.publish_queue,
            payload=payload,
        )


        logger.info("Recognition task sent task_id={} uploaded_image_id={}", task.id, uploaded_image_id)
        return task

    async def accept_cv_result(
        self,
        task_id: str,
        cv_response: dict[str, Any],
    ) -> None:
        logger.debug(
            "Accepting CV result for task_id={}",
            task_id,
        )

        result = await self._require_result(task_id)

        status = result.status

        if status == "accepting_results":
            status = "waiting_for_ocr"

        elif status == "waiting_for_cv":
            status = "resolving"

        elif status in ["resolving", "completed", "failed"]:
            logger.warning(
                "CV result for task_id={} cannot be accepted in status={}",
                task_id,
                result.status,
            )
            return

        else:
            raise ValueError(
                f"Unexpected status for task_id={task_id}: {result.status}"
            )

        await self._result_repository.update(
            result_id=task_id,
            cv_response=cv_response,
            status=status,
        )

        if status == "resolving":
            await self._resolve(task_id)

    async def accept_ocr_result(
        self,
        task_id: str,
        ocr_response: dict[str, Any],
    ) -> None:
        logger.debug(
            "Accepting OCR result for task_id={}",
            task_id,
        )

        result = await self._require_result(task_id)

        status = result.status

        if status == "accepting_results":
            status = "waiting_for_cv"

        elif status == "waiting_for_ocr":
            status = "resolving"

        elif status in ["resolving", "completed", "failed"]:
            logger.warning(
                "OCR result for task_id={} cannot be accepted in status={}",
                task_id,
                result.status,
            )
            return

        else:
            raise ValueError(
                f"Unexpected status for task_id={task_id}: {result.status}"
            )

        await self._result_repository.update(
            result_id=task_id,
            ocr_response=ocr_response,
            status=status,
        )

        if status == "resolving":
            await self._resolve(task_id)
        

    async def _require_task(self, task_id: str) -> RecognitionTask:
        task = await self._task_repository.get_by_id(task_id)
        if task is None:
            logger.error("Recognition task not found task_id={}", task_id)
            raise ValueError(f"Recognition task with id {task_id} not found")
        return task

    async def _require_result(self, task_id: str) -> RecognitionResult:
        result = await self._result_repository.get_by_id(task_id)
        if result is None:
            logger.error("Recognition result not found for task_id={}", task_id)
            raise ValueError(f"Recognition result with id {task_id} not found")
        return result

    async def _resolve(self, task_id: str) -> None:
        logger.debug("Resolving recognition result for task_id={}", task_id)
        result = await self._require_result(task_id)

        cv_response = CVInferenceResponse.model_validate(
            result.cv_response,
        )
        ocr_response = OCRInferenceResponse.model_validate(
            result.ocr_response,
        )

        cv_slug = self._resolver.get_cv_slug(cv_response)
        ocr_slug = self._resolver.get_ocr_slug(ocr_response)

        cv_wine = None

        if cv_slug is not None:
            cv_wine = await self._wine_repository.get_by_slug(
                cv_slug,
            )

        ocr_wine = None

        if ocr_slug is not None:
            ocr_wine = await self._wine_repository.get_by_slug(
                ocr_slug,
            )

        resolution = self._resolver.resolve(
            cv_response=cv_response,
            ocr_response=ocr_response,
            cv_wine=cv_wine,
            ocr_wine=ocr_wine,
        )

        if not resolution.resolved:

            logger.error(
                "Recognition result resolution failed for task_id={} error={}",
                task_id,
                resolution.error,
            )

            await self._result_repository.update(
                result_id=task_id,
                status="failed",
                error_message=resolution.error,
                finished_at=datetime.utcnow(),
            )
            return

        await self._result_repository.update(
            result_id=task_id,
            status="completed",
            detected_slug=resolution.detected_slug,
            alternatives=resolution.alternatives,
            error_message=None,
            finished_at=datetime.utcnow(),
        )

    async def _get_or_fetch_wine(
        self,
        slug: str,
    ) -> Wine:
        logger.debug("Fetching wine by slug={} from database", slug)
        wine = await self._wine_repository.get_by_slug(
            slug,
        )

        if wine is not None:
            return wine

        logger.debug("Wine not found in database, fetching from source slug={}", slug)
        parsed_wine = await self._wine_parser.fetch(slug)

        return await self._wine_repository.create(
            **parsed_wine.model_dump(),
        )

    async def get_result(
        self,
        task_id: str,
    ) -> RecognitionResponse:
        logger.debug("Fetching recognition result for task_id={}", task_id)
        result = await self._require_result(task_id)

        detected_wine = None

        if result.detected_slug is not None:
            detected_wine = await self._get_or_fetch_wine(
                result.detected_slug,
            )

        alternatives: list[Wine] = []

        for slug in result.alternatives or []:
            alternatives.append(
                await self._get_or_fetch_wine(slug),
            )

        return RecognitionResponse(
            task_id=task_id,
            status=result.status, #type: ignore
            detected_wine=(
                WineDTO.model_validate(detected_wine)
                if detected_wine is not None
                else None
            ),
            alternatives=[
                WineDTO.model_validate(wine)
                for wine in alternatives
            ],
            error=result.error_message,
            finished_at=result.finished_at,
            elapsed_time=(result.finished_at - result.created_at).total_seconds() if result.finished_at and result.status == "completed" else None
        )