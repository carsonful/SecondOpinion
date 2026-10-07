from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SecondOpinion API"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str = "postgresql+psycopg://secondopinion:secondopinion@localhost:5432/secondopinion"
    ncbi_email: str | None = None
    ncbi_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
