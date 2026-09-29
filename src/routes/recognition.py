import asyncio
import json
import time
from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger
from src.models.recognition import CreateRecognitionTaskRequest
from src.resources import Resources
from src.services.factories import ServiceFactory

from io import BytesIO

from PIL import Image

TERMINAL_STATUSES = {"completed", "failed"}
POLL_INTERVAL_SECONDS = 0.5
# Держим ниже таймаута прокси (у nginx по умолчанию 60 с)
WAIT_TIMEOUT_SECONDS = 10.0

# Меньше --max-time 10 у скрипта, чтобы успеть ответить до обрыва
EVAL_WAIT_TIMEOUT_SECONDS = 8.5
# Частый опрос, чтобы не раздувать latency_ms
EVAL_POLL_INTERVAL_SECONDS = 0.1

class RecognitionController:

    def __init__(self, router: APIRouter, resources: Resources, service_factory: ServiceFactory):
        self._router = router
        self._resources = resources
        self._service_factory = service_factory

        self._router.post("")(self.create_task)
        self._router.post("/sync")(self.recognize_sync)
        self._router.get("/{task_id}")(self.get_result)

        logger.info(
            "RecognitionController initialized with routes: POST /, POST /sync, GET /{task_id}"
        )

    async def _prepare_request(
        self,
        image: UploadFile,
        crop: bool = True,
    ) -> CreateRecognitionTaskRequest:
        raw_bytes = await image.read()

        processed_bytes, content_type, extension = self._preprocess_image(
            raw_bytes,
        )

        return CreateRecognitionTaskRequest(
            image_bytes=processed_bytes,
            content_type=content_type,
            extension=extension,
        )

    @staticmethod
    def _preprocess_image(
        image_bytes: bytes,
        *,
        crop_x: float = 0.0,
        crop_y: float = 0.0,
        crop_width: float = 1.0,
        crop_height: float = 1.0,
        crop: bool = True,
    ) -> tuple[bytes, str, str]:
        try:
            image = Image.open(BytesIO(image_bytes))
            image.load()
        except Exception as e:
            raise ValueError("Не удалось декодировать изображение.") from e

        image_format = image.format

        if not image_format:
            raise ValueError("Не удалось определить формат изображения.")

        content_type = Image.MIME.get(image_format)

        if not content_type:
            raise ValueError(
                f"Не удалось определить MIME-тип изображения формата {image_format}."
            )

        extension_by_format = {
            "JPEG": ".jpg",
            "PNG": ".png",
            "WEBP": ".webp",
            "GIF": ".gif",
            "BMP": ".bmp",
            "TIFF": ".tiff",
            "AVIF": ".avif",
        }

        extension = extension_by_format.get(image_format)

        if not extension:
            raise ValueError(
                f"Не удалось определить расширение изображения формата {image_format}."
            )

        logger.debug(
            "Decoded input image format={} content_type={} extension={} size={}x{}",
            image_format,
            content_type,
            extension,
            image.width,
            image.height,
        )

        if not 0 <= crop_x <= 1:
            raise ValueError("crop_x должен быть в диапазоне [0, 1].")
        if not 0 <= crop_y <= 1:
            raise ValueError("crop_y должен быть в диапазоне [0, 1].")
        if not 0 < crop_width <= 1:
            raise ValueError("crop_width должен быть в диапазоне (0, 1].")
        if not 0 < crop_height <= 1:
            raise ValueError("crop_height должен быть в диапазоне (0, 1].")
        if crop_x + crop_width > 1:
            raise ValueError("Область crop выходит за правую границу изображения.")
        if crop_y + crop_height > 1:
            raise ValueError("Область crop выходит за нижнюю границу изображения.")

        transformed = False

        if crop:
            left = round(image.width * crop_x)
            top = round(image.height * crop_y)
            right = round(image.width * (crop_x + crop_width))
            bottom = round(image.height * (crop_y + crop_height))

            if right <= left or bottom <= top:
                raise ValueError("Некорректная область кадрирования.")

            image = image.crop((left, top, right, bottom))
            transformed = True

        factor = min(1.0, 1440 / max(image.width, image.height))

        if factor < 1.0:
            image = image.resize(
                (
                    round(image.width * factor),
                    round(image.height * factor),
                ),
                Image.Resampling.LANCZOS,
            )
            transformed = True

        if not transformed:
            return image_bytes, content_type, extension

        output = BytesIO()

        try:
            image.save(output, format=image_format)
        except Exception as e:
            raise ValueError(
                f"Не удалось сохранить изображение в исходном формате {image_format}."
            ) from e

        return output.getvalue(), content_type, extension

    # ---------- helpers ----------

    async def _submit_task(self, request: CreateRecognitionTaskRequest) -> str:
        async with self._resources.connection_manager.acquire() as session:
            recognition_service = self._service_factory.recognition_service(session)
            image_service = self._service_factory.image_service(session)

            uploaded_image = await image_service.upload_client_image(
                image_bytes=request.image_bytes,
                content_type=request.content_type,
                extension=request.extension,
            )

            task = await recognition_service.create_and_send_task(
                uploaded_image_id=uploaded_image.id,
                object_key=uploaded_image.object_key,
            )

            return str(task.id)

    async def _fetch_result(self, task_id: str):
        # Новая сессия на каждый опрос: не держим соединение с БД всё время ожидания
        # и не читаем устаревший снимок из долгой транзакции.
        async with self._resources.connection_manager.acquire() as session:
            recognition_service = self._service_factory.recognition_service(session)
            return await recognition_service.get_result(task_id=task_id)

    # ---------- routes ----------

    async def create_task(
        self,
        image: Annotated[UploadFile, File(...)],
        crop: Annotated[bool, Form(...)] = True,
    ):
        logger.debug(
            "Received request to create recognition task filename={} content_type={}",
            image.filename,
            image.content_type,
        )

        try:
            request = await self._prepare_request(image)

            async with self._resources.connection_manager.acquire() as session:
                recognition_service = self._service_factory.recognition_service(session)
                image_service = self._service_factory.image_service(session)

                uploaded_image = await image_service.upload_client_image(
                    image_bytes=request.image_bytes,
                    content_type=request.content_type,
                    extension=request.extension,
                )

                task = await recognition_service.create_and_send_task(
                    uploaded_image_id=uploaded_image.id,
                    object_key=uploaded_image.object_key,
                )

                return Response(
                    content=str(task.id),
                    status_code=202,
                )

        except Exception as e:
            logger.exception("Error creating recognition task error={}", e)
            return Response(
                content="Internal Server Error",
                status_code=500,
            )

    async def recognize_sync(
        self,
        image: Annotated[UploadFile, File(...)],
    ):
        logger.debug(
            "Received sync recognition request filename={} content_type={}",
            image.filename,
            image.content_type,
        )

        try:
            request = await self._prepare_request(image)
            task_id = await self._submit_task(request)
        except Exception as e:
            logger.exception("Error creating recognition task error={}", e)
            return Response(
                content="Internal Server Error",
                status_code=500,
            )

        deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS

        while True:
            try:
                result = await self._fetch_result(task_id)
            except Exception as e:
                logger.exception("Error fetching recognition result error={}", e)
                return Response(
                    content="Internal Server Error",
                    status_code=500,
                )

            if result is not None and result.status in TERMINAL_STATUSES:
                logger.debug(
                    "Sync recognition finished task_id={} status={}",
                    task_id,
                    result.status,
                )

                return Response(
                    content=result.model_dump_json(),
                    media_type="application/json",
                    status_code=200,
                )

            if time.monotonic() >= deadline:
                logger.warning("Sync recognition timed out task_id={}", task_id)

                return Response(
                    content=json.dumps(
                        {
                            "detail": "Recognition is still in progress",
                            "task_id": task_id,
                        }
                    ),
                    media_type="application/json",
                    status_code=504,
                )

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def get_result(self, task_id: str):
        logger.debug("Received request to get recognition result task_id={}", task_id)

        async with self._resources.connection_manager.acquire() as session:
            try:
                recognition_service = self._service_factory.recognition_service(session)
                result = await recognition_service.get_result(task_id=task_id)

                
                if result is None:
                    logger.warning("Recognition result not found task_id={}", task_id)
                    return Response(
                        content="Recognition result not found",
                        status_code=404,
                    )
                logger.debug(
                    "Recognition result fetched task_id={} body={}", task_id, result.model_dump_json()
                )
                return Response(
                    content=result.model_dump_json(),
                    media_type="application/json",
                    status_code=200,
                )

            except Exception as e:
                logger.exception("Error fetching recognition result error={}", e)
                return Response(
                    content="Internal Server Error",
                    status_code=500,
                )

    async def _wait_for_result(self, task_id: str, timeout: float, interval: float):
        """Возвращает результат в терминальном статусе или None по таймауту."""
        deadline = time.monotonic() + timeout
        while True:
            result = await self._fetch_result(task_id)
            if result is not None and result.status in TERMINAL_STATUSES:
                return result
            if time.monotonic() >= deadline:
                return None
            await asyncio.sleep(interval)

    async def eval_predict(
        self,
        image: Annotated[UploadFile, File(...)],
    ):
        try:
            request = await self._prepare_request(image)

            task_id = await self._submit_task(request)

            result = await self._wait_for_result(
                task_id,
                timeout=EVAL_WAIT_TIMEOUT_SECONDS,
                interval=EVAL_POLL_INTERVAL_SECONDS,
            )

        except Exception as e:
            logger.exception("Eval prediction failed error={}", e)
            return Response(
                content="Internal Server Error",
                status_code=500,
            )

        if result is None:
            logger.warning("Eval prediction timed out task_id={}", task_id)
            return Response(
                content="Recognition timed out",
                status_code=504,
            )

        slug = None

        if result.status == "completed" and result.detected_wine is not None:
            slug = result.detected_wine.slug

        return JSONResponse({"slug": slug})