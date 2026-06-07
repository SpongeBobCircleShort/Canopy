from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Canopy API"
    database_url: str = "postgresql+psycopg://canopy_user:canopy_password@localhost:5432/canopy"
    jwt_secret: str = "change-me-in-production"
    audio_storage_path: str = "/tmp/canopy-audio"
    audio_model_path: str | None = None
    metrics_path: str | None = None
    fusion_auto_interval_minutes: int = 0  # 0 = disabled

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
