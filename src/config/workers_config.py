from pydantic import Field
from pydantic_settings import BaseSettings


class WorkersConfig(BaseSettings):
    worker_name: str = Field(default="worker")
    publish_queue: str = Field(default="publish_queue")
    consume_queue: str = Field(default="consume_queue")