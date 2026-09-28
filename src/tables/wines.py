from datetime import datetime

from sqlalchemy import Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.tables import Base


class Wine(Base):
    __tablename__ = "wines"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    slug: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
    )

    wine_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    producer: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    region: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    style: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
    )

    color: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    grapes: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
    )

    year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    alcohol_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    image_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    aliases: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
    )

    search_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=False,
    )