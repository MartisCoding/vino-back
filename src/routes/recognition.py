from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile
from loguru import logger

from src.models.recognition import CreateRecognitionTaskRequest
from src.resources import Resources
from src.services.factories import ServiceFactory


class RecognitionController:

    def __init__(self, router: APIRouter, resources: Resources, service_factory: ServiceFactory):
        self._router = router
        self._resources = resources
        self._service_factory = service_factory

        self._router.post("")(self.create_task)
        self._router.get("/{task_id}")(self.get_result)

        logger.info("RecognitionController initialized with routes: POST /, GET /{task_id}")

    async def create_task(
        self,
        image: Annotated[UploadFile, File(...)],
    ):
        logger.debug(
            "Received request to create recognition task filename={} content_type={}",
            image.filename,
            image.content_type,
        )
    
        image_bytes = await image.read()
    
        request = CreateRecognitionTaskRequest(
            image_bytes=image_bytes,
            content_type=image.content_type or "application/octet-stream",
        )
    
        async with self._resources.connection_manager.acquire() as session:
            try:
                recognition_service = self._service_factory.recognition_service(session)
                image_service = self._service_factory.image_service(session)
    
                uploaded_image = await image_service.upload_client_image(
                    image_bytes=request.image_bytes,
                    content_type=request.content_type,
                )
    
                task = await recognition_service.create_and_send_task(
                    uploaded_image_id=uploaded_image.id,
                    object_key=uploaded_image.object_key,
                )
    
                return Response(
                    content=task.id,
                    status_code=202,
                )
    
            except Exception as e:
                logger.exception("Error creating recognition task error={}", e)
                return Response(
                    content="Internal Server Error",
                    status_code=500,
                )

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