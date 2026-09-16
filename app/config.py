from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Invoice Processing API"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://invoice:invoice@localhost:5432/invoice_processing"
    storage_dir: Path = Path("storage")
    max_upload_bytes: int = 5 * 1024 * 1024
    processing_mode: Literal["sync", "celery"] = "sync"
    celery_broker_url: str = "redis://localhost:6379/0"
    api_key: SecretStr | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def require_production_api_key(self) -> "Settings":
        if self.app_env == "production" and (
            self.api_key is None or len(self.api_key.get_secret_value()) < 32
        ):
            raise ValueError("Production requires an API_KEY of at least 32 characters.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
