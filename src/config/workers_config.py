from pydantic import Field

from src.config import AppSettings


class WorkersConfig(AppSettings):
    worker_name: str = Field(default="worker")
    publish_queue: str = Field(default="publish_queue")
    consume_queue: str = Field(default="consume_queue")