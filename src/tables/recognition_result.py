import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from src.tables import Base


class RecognitionResult(Base):
    __tablename__ = "recognition_results"

    # One-to-one relationship with RecognitionTask
    id: Mapped[str] = mapped_column(
        ForeignKey("recognition_tasks.id"),
        primary_key=True,
    )

    # Theese field are used to store the raw response data from workers
    ocr_response: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    cv_response: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
            Enum(
                "accepting_results",
                "waiting_for_ocr",
                "waiting_for_cv",
                "resolving",
                "fetching_wines",
                "partially_resolved",
                "completed",
                "failed",
                name="recognition_task_status",
            ),
            nullable=False,
        )

    error_message: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    detected_slug: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    alternatives: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(255)),
        nullable=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )