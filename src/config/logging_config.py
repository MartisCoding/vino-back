from pathlib import Path

from pydantic import Field

from src.config import AppSettings


class LoggingConfig(AppSettings):
    level: str = Field(default="INFO")
    logs_directory: str = Field(default="./logs/")
    file: str | None = Field(default=None)
    serialize: bool = Field(default=False)
    
    @property
    def log_path(self) -> str | None:
        if not self.file:
            return None

        return str(Path(self.logs_directory) / self.file)