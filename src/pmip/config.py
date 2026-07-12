"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute project root — avoids empty DB when API starts from a different cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "pmip.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = f"sqlite:///{DEFAULT_DB_PATH}"
    fred_api_key: str = ""
    polygon_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    news_api_key: str = ""
    mlflow_tracking_uri: str = f"file:{PROJECT_ROOT / 'mlruns'}"
    model_registry_path: str = str(PROJECT_ROOT / "models")
    environment: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
