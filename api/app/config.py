from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Canopy API"
    database_url: str = "postgresql+psycopg://canopy_user:canopy_password@localhost:5432/canopy"
    jwt_secret: str = "change-me-in-production"
    audio_storage_path: str = "/tmp/canopy-audio"
    audio_model_path: str | None = None
    anomaly_model_path: str | None = None
    metrics_path: str | None = None
    fusion_auto_interval_minutes: int = 0  # 0 = disabled
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_address: str | None = None
    smtp_use_tls: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"  # comma-separated
    log_level: str = "INFO"
    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = 10
    rate_limit_global_per_minute: int = 120

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
