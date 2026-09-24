from typing import Literal

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.repositories import WineRepository
from src.services import ServiceFactory
from src.tables import RecognitionTask, Wine
from src.resources.database import ConnectionManager

router = APIRouter(prefix="/recognition", tags=["recognition"])


class TaskCreatedResponse(BaseModel):
    task_id: str
    status: str
    uploaded_image_id: int
    status_url: str


class WorkerConfirmRequest(BaseModel):
    status: Literal["completed", "failed"]
    detected_wine_id: int | None = None
    detected_wine_slug: str | None = None
    error: str | None = None


class WineResponse(BaseModel):
    id: int
    external_id: str
    name: str
    country: str
    region: str
    winery: str
    rating: float
    description: str
    source_url: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    detected_wine_slug: str | None = None
    error: str | None = None
    wine: WineResponse | None = None
    source_checked: bool = False
    source_wine_exists: bool | None = None
    fallback_message: str | None = None
    similar_wines: list[WineResponse] = []


def _wine_to_response(wine: Wine) -> WineResponse:
    return WineResponse(
        id=wine.id,
        external_id=wine.external_id,
        name=wine.name,
        country=wine.country,
        region=wine.region,
        winery=wine.winery,
        rating=wine.rating,
        description=wine.description,
        source_url=wine.source_url,
    )

def _get_app_dependencies(request: Request) -> tuple[Config, ConnectionManager, ServiceFactory]:
    config: Config = request.app.state.config
    connection_manager = request.app.state.connection_manager
    service_factory: ServiceFactory = request.app.state.service_factory
    return config, connection_manager, service_factory

async def _resolve_task_wine(
    task: RecognitionTask,
    session: AsyncSession,
    service_factory: ServiceFactory,
    wine_repository: WineRepository,
) -> tuple[Wine | None, bool, bool | None, list[Wine], str | None]:
    detected_slug = task.detected_wine_external_id
    if not detected_slug:
        return None, False, None, [], None

    wine = await wine_repository.get_by_external_id(detected_slug)
    if wine is not None:
        return wine, False, True, [], None

    parser_service = service_factory.create_wine_parser_service(session)
    try:
        parsed_wine = await parser_service.parse_and_save(detected_slug)
        logger.info(
            "Wine parsed from source and saved slug={} task_id={} wine_id={}",
            detected_slug,
            task.id,
            parsed_wine.id,
        )
        return parsed_wine, True, True, [], None
    except (httpx.HTTPError, ValueError) as error:
        logger.warning(
            "Wine parsing failed slug={} task_id={} error={}",
            detected_slug,
            task.id,
            error,
        )
    finally:
        await parser_service.close()

    similar = await wine_repository.find_similar_by_external_id(detected_slug, limit=3)
    return (
        None,
        True,
        False,
        list(similar),
        "Данного вина нет в нашей БД и на источнике, попробуйте похожие варианты.",
    )


@router.post("/tasks", response_model=TaskCreatedResponse)
async def create_recognition_task(request: Request, image: UploadFile = File(...)) -> TaskCreatedResponse:
    logger.debug("Received recognition task create request filename={} content_type={}", image.filename, image.content_type)
    if not image.content_type:
        raise HTTPException(status_code=400, detail="Image content type is required.")

    _, connection_manager, service_factory = _get_app_dependencies(request)
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    async with connection_manager.acquire() as session:
        image_service = service_factory.create_image_service(session)
        task_service = service_factory.create_recognition_task_service(session)

        uploaded_image = await image_service.upload_client_image(image_bytes=image_bytes, content_type=image.content_type)
        task = await task_service.create_and_send_task(uploaded_image_id=uploaded_image.id)
        await session.commit()

    logger.info("Recognition task created task_id={} uploaded_image_id={}", task.id, uploaded_image.id)
    return TaskCreatedResponse(
        task_id=task.id,
        status=task.status,
        uploaded_image_id=uploaded_image.id,
        status_url=f"/recognition/tasks/{task.id}",
    )


@router.post("/tasks/{task_id}/confirm", response_model=TaskStatusResponse)
async def confirm_recognition_task(task_id: str, payload: WorkerConfirmRequest, request: Request) -> TaskStatusResponse:
    logger.debug("Received recognition task confirmation task_id={} status={}", task_id, payload.status)
    _, connection_manager, service_factory = _get_app_dependencies(request)
    async with connection_manager.acquire() as session:
        wine_repository = service_factory.create_wine_repository(session)
        task_service = service_factory.create_recognition_task_service(session)

        try:
            task = await task_service.confirm_task(
                task_id=task_id,
                status=payload.status,
                detected_wine_id=payload.detected_wine_id,
                detected_wine_external_id=payload.detected_wine_slug,
                error=payload.error,
            )
        except ValueError as error:
            status_code = 404 if "does not exist" in str(error) else 400
            raise HTTPException(status_code=status_code, detail=str(error)) from error

        await session.commit()

        wine = None
        source_checked = False
        source_wine_exists: bool | None = None
        similar_wines: list[Wine] = []
        fallback_message = None
        if task.status == "completed":
            wine, source_checked, source_wine_exists, similar_wines, fallback_message = await _resolve_task_wine(
                task,
                session,
                service_factory,
                wine_repository,
            )
            await session.commit()

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status,
        detected_wine_slug=task.detected_wine_external_id,
        error=task.error,
        wine=_wine_to_response(wine) if wine is not None else None,
        source_checked=source_checked,
        source_wine_exists=source_wine_exists,
        fallback_message=fallback_message,
        similar_wines=[_wine_to_response(item) for item in similar_wines],
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_recognition_task_status(task_id: str, request: Request) -> TaskStatusResponse:
    logger.debug("Received recognition task status request task_id={}", task_id)
    _, connection_manager, service_factory = _get_app_dependencies(request)
    async with connection_manager.acquire() as session:
        wine_repository = service_factory.create_wine_repository(session)
        task_repository = service_factory.create_recognition_task_repository(session)
        task = await task_repository.get_by_id(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Recognition task with id={task_id} was not found.")

        wine = None
        source_checked = False
        source_wine_exists: bool | None = None
        similar_wines: list[Wine] = []
        fallback_message = None
        if task.status == "completed":
            wine, source_checked, source_wine_exists, similar_wines, fallback_message = await _resolve_task_wine(
                task,
                session,
                service_factory,
                wine_repository,
            )
            await session.commit()

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status,
        detected_wine_slug=task.detected_wine_external_id,
        error=task.error,
        wine=_wine_to_response(wine) if wine is not None else None,
        source_checked=source_checked,
        source_wine_exists=source_wine_exists,
        fallback_message=fallback_message,
        similar_wines=[_wine_to_response(item) for item in similar_wines],
    )
