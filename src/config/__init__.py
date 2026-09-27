from contextvars import ContextVar
from functools import lru_cache

from loguru import logger
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from src.config.cors import FastAPICORSConfig
from src.config.database_config import DatabaseConfig
from src.config.fastapi_config import FastAPIConfig
from src.config.logging_config import LoggingConfig
from src.config.minio_config import MinioConfig
from src.config.parser_config import ParserConfig
from src.config.rabbitmq_config import RabbitMQConfig
from src.config.workers_config import WorkersConfig

_settings_sources_enabled = ContextVar(
    "settings_sources_enabled",
    default=True,
)


class AppSettings(BaseSettings):

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        if not _settings_sources_enabled.get():
            return (init_settings,)

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

    @classmethod
    def defaults(cls):
        token = _settings_sources_enabled.set(False)

        try:
            return cls()
        finally:
            _settings_sources_enabled.reset(token)


class Config(AppSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        env_nested_delimiter="__",
        extra="ignore"
    )
    
    app_name: str = Field(default="test")
    app_version: str = Field(default="0.0.1")
    
    
    fastapi: FastAPIConfig = Field(default_factory=FastAPIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    minio: MinioConfig = Field(default_factory=MinioConfig)
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig)
    parser: ParserConfig = Field(default_factory=ParserConfig)
 
@lru_cache   
def config() -> Config:
    logger.debug("Building application config from environment")
    return Config()