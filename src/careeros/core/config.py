from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "CareerOS"
    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_url: str
    api_token: SecretStr
    storage_root: Path = Path("data/incoming")
    max_upload_size_bytes: int = 10 * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

