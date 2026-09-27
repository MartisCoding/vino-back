from pydantic import Field

from src.config import AppSettings


class MinioConfig(AppSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=9000)
    access_key: str = Field(default="minioadmin")
    secret_key: str = Field(default="minioadmin")
    image_bucket: str = Field(default="images")