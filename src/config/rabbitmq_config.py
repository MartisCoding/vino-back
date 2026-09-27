from pydantic import Field

from src.config import AppSettings
from src.config.workers_config import WorkersConfig


class RabbitMQConfig(AppSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5672)
    user: str = Field(default="guest")
    password: str = Field(default="guest")
    virtual_host: str = Field(default="/")

    inference_worker: WorkersConfig = Field(default_factory=WorkersConfig)
    inference_ocr_worker: WorkersConfig = Field(default_factory=WorkersConfig)
    
    @property
    def url(self) -> str:
        vhost = self.virtual_host if self.virtual_host.startswith("/") else f"/{self.virtual_host}"
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}{vhost}"


