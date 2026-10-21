from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore"
    )

    azure_foundry_endpoint: str | None = None
    azure_foundry_deployment: str | None = None
    azure_foundry_api_key: SecretStr | None = None

    app_name: str = "SecondOpinion API"
    cors_origins: list[str] = ["http://localhost:5173"]

    # NCBI E-utilities. An API key raises the rate limit from 3 to 10 requests/second.
    # NCBI asks every client to identify itself with a tool name and contact email.
    ncbi_api_key: str | None = None
    ncbi_email: str | None = None
    ncbi_tool: str = "SecondOpinion"

    # Unpaywall requires a real contact email; falls back to NCBI_EMAIL when unset.
    unpaywall_email: str | None = None

    # Azure AI Document Intelligence parses open-access PDFs (prebuilt layout model).
    # Without both values, studies that only have a PDF fall back to their abstract.
    azure_document_intelligence_endpoint: str | None = None
    azure_document_intelligence_api_key: SecretStr | None = None

    # Full-text retrieval: where records are cached, how many studies are fetched
    # at once, how long one study may take, and its token budget in a Foundry prompt.
    full_text_cache_dir: Path = Path(__file__).resolve().parents[1] / ".cache" / "full_text"
    full_text_concurrency: int = Field(default=4, ge=1, le=16)
    full_text_study_timeout: float = Field(default=45.0, gt=0)
    study_token_budget: int = Field(default=6000, ge=500)


@lru_cache
def get_settings() -> Settings:
    return Settings()
