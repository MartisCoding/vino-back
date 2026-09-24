from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from loguru import logger

class ParserConfig(BaseSettings):
    base_url: str = Field(default="https://vino-svoe.ru")
    timeout: int = Field(default=10)
    max_retries: int = Field(default=3)
    retry_delay: int = Field(default=1)


class FastAPIConfig(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)
    title: str = Field(default="app-test")


class LoggingConfig(BaseSettings):
    level: str = Field(default="INFO")
    logs_directory: str = Field(default="./logs/")
    file: str | None = Field(default=None)
    serialize: bool = Field(default=False)
    
    @property
    def log_path(self) -> str:
        path = self.logs_directory + self.file if self.file else ""
        return path
    
    
class DatabaseConfig(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="postgres")
    password: str = Field(default="postgres")
    database: str = Field(default="mydb")
    
    @property
    def url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )
        
              
class MinioConfig(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=9000)
    access_key: str = Field(default="minioadmin")
    secret_key: str = Field(default="minioadmin")
    image_bucket: str = Field(default="images")
    
    
class RabbitMQConfig(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5672)
    user: str = Field(default="guest")
    password: str = Field(default="guest")
    virtual_host: str = Field(default="/")
    recognition_queue: str = Field(default="recognition.tasks")

    @property
    def url(self) -> str:
        vhost = self.virtual_host if self.virtual_host.startswith("/") else f"/{self.virtual_host}"
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}{vhost}"


class Config(BaseSettings):
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
    
def config() -> Config:
    logger.debug("Building application config from environment")
    return Config()


def generate_env_file(config: Config, file_path: str = ".env") -> None:
    logger.debug("Generating env file at path={}", file_path)
    env_string = dump_env_string(config)
    with open(file_path, "w") as env_file:
        env_file.write(env_string)
    logger.info("Env file generated at path={}", file_path)

def dump_env_string(config: Config) -> str:
    logger.debug("Dumping env string from current config")
    env_string = (
        f"APP_NAME={config.app_name}\n"
        f"APP_VERSION={config.app_version}\n"
        f"FASTAPI__HOST={config.fastapi.host}\n"
        f"FASTAPI__PORT={config.fastapi.port}\n"
        f"FASTAPI__DEBUG={config.fastapi.debug}\n"
        f"FASTAPI__TITLE={config.fastapi.title}\n"
        f"LOGGING__LEVEL={config.logging.level}\n"
        f"LOGGING__LOGS_DIRECTORY={config.logging.logs_directory}\n"
        f"LOGGING__FILE={config.logging.file}\n"
        f"LOGGING__SERIALIZE={config.logging.serialize}\n"
        f"DATABASE__HOST={config.database.host}\n"
        f"DATABASE__PORT={config.database.port}\n"
        f"DATABASE__USER={config.database.user}\n"
        f"DATABASE__PASSWORD={config.database.password}\n"
        f"DATABASE__DATABASE={config.database.database}\n"
        f"MINIO__HOST={config.minio.host}\n"
        f"MINIO__PORT={config.minio.port}\n"
        f"MINIO__ACCESS_KEY={config.minio.access_key}\n"
        f"MINIO__SECRET_KEY={config.minio.secret_key}\n"
        f"MINIO__IMAGE_BUCKET={config.minio.image_bucket}\n"
        f"RABBITMQ__HOST={config.rabbitmq.host}\n"
        f"RABBITMQ__PORT={config.rabbitmq.port}\n"
        f"RABBITMQ__USER={config.rabbitmq.user}\n"
        f"RABBITMQ__PASSWORD={config.rabbitmq.password}\n"
        f"RABBITMQ__VIRTUAL_HOST={config.rabbitmq.virtual_host}\n"
        f"RABBITMQ__RECOGNITION_QUEUE={config.rabbitmq.recognition_queue}\n"
        f"PARSER__BASE_URL={config.parser.base_url}\n"
        f"PARSER__TIMEOUT={config.parser.timeout}\n"
        f"PARSER__MAX_RETRIES={config.parser.max_retries}\n"
        f"PARSER__RETRY_DELAY={config.parser.retry_delay}\n"
    )
    logger.debug("Env string prepared")
    return env_string
