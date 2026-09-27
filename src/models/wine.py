# src/models/wine.py

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WineDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    name: str
    country: str
    region: str
    winery: str
    rating: float
    description: str
    source_url: str
    created_at: datetime
    updated_at: datetime


class ParsedWine(BaseModel):
    external_id: str
    name: str
    country: str
    region: str
    winery: str
    rating: float
    description: str
    source_url: str