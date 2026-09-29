# src/models/recognition.py

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.models.wine import WineDTO


class RecognitionResponse(BaseModel):
    task_id: str
    status: Literal[
        "accepting_results",
        "waiting_for_ocr",
        "waiting_for_cv",
        "resolving",
        "partially_resolved",
        "completed",
        "failed",
    ]

    detected_wine: WineDTO | None = None
    alternatives: list[WineDTO] = Field(default_factory=list)

    error: str | None = None
    finished_at: datetime | None = None
    elapsed_time: float | None = None



class CreateRecognitionTaskRequest(BaseModel):
    image_bytes: bytes = Field(min_length=1)
    content_type: str
    extension: str | None = None

    # @field_validator("content_type")
    # @classmethod
    # def validate_content_type(cls, value: str) -> str:
    #     if not value.startswith("image/") or "application/octet-stream" in value:
    #         raise ValueError("Uploaded file must be an image")

    #     return value