from pydantic import Field

from src.config import AppSettings
from src.config.cors import FastAPICORSConfig


class FastAPIConfig(AppSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)
    title: str = Field(default="app-test")
    cors: FastAPICORSConfig = Field(default_factory=FastAPICORSConfig)


    