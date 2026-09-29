# src/models/wine.py

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WineDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    wine_id: str
    name: str
    producer: str
    region: str
    style: list[str]
    color: str
    grapes: list[str]
    year: int | None
    alcohol_percent: float | None
    image_url: str | None
    aliases: list[dict]
    search_text: str
    created_at: datetime
    updated_at: datetime


class ParsedWine(BaseModel):
    slug: str
    name: str
    country: str
    region: str
    winery: str
    rating: float
    description: str
    source_url: str