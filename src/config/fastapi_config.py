from pydantic import Field
from pydantic_settings import BaseSettings


class FastAPIConfig(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)
    title: str = Field(default="app-test")
    