from pydantic import Field

from src.config import AppSettings


class FastAPICORSConfig(AppSettings):
    allow_origins: list[str] = Field(default=["*"])
    allow_credentials: bool = Field(default=False)
    allow_methods: list[str] = Field(default=["*"])
    allow_headers: list[str] = Field(default=["*"])