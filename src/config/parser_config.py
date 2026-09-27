from pydantic import Field
from pydantic_settings import BaseSettings


class ParserConfig(BaseSettings):
    base_url: str = Field(default="https://vino-svoe.ru")
    timeout: int = Field(default=10)
    max_retries: int = Field(default=3)
    retry_delay: int = Field(default=1)