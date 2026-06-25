from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


EmbeddingProviderName = Literal["sentence-transformers", "deterministic"]


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
    embedding_provider: EmbeddingProviderName = "sentence-transformers"
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    embedding_version: str = "bge-small-en-v1.5:sentence-transformers:v1"
    embedding_dimension: int = 384
    scoring_version: str = "hybrid:v1"

    @field_validator("embedding_provider", mode="before")
    @classmethod
    def normalize_embedding_provider(cls, value: object) -> object:
        if isinstance(value, str) and value == "sentence_transformers":
            return "sentence-transformers"
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
