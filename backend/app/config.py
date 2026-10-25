from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore"
    )

    azure_foundry_endpoint: str | None = None
    azure_foundry_deployment: str | None = None
    azure_foundry_api_key: SecretStr | None = None
    database_url: SecretStr | None = None

    app_name: str = "SecondOpinion API"
    cors_origins: list[str] = ["http://localhost:5173"]

    # NCBI E-utilities. An API key raises the rate limit from 3 to 10 requests/second.
    # NCBI asks every client to identify itself with a tool name and contact email.
    ncbi_api_key: str | None = None
    ncbi_email: str | None = None
    ncbi_tool: str = "SecondOpinion"

    # Crossref. Sending a contact email moves us into the "polite" pool, which allows
    # 10 requests/second and 3 at once instead of 5 requests/second, 1 at a time.
    crossref_mailto: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
