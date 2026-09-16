"""
app/config.py

Reads settings from environment variables (.env). Everything else in the
app imports `get_settings()` rather than reading os.environ directly, so
there's one source of truth for configuration.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_env: str = "development"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    # --- Local LLM (any OpenAI-compatible server: LM Studio, Ollama, vLLM, etc.) ---
    local_llm_base_url: str = "http://localhost:1234/v1"
    local_llm_model: str = "nvidia/nemotron-3-nano-4b"
    local_llm_api_key: str = "local"
    local_llm_timeout_seconds: float = 12.0

    # --- Claude fallback ---
    # llm_primary_provider: "claude" or "local" — whichever is NOT primary
    # becomes the automatic fallback if the primary fails or times out.
    llm_primary_provider: str = "claude"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # --- Map / location ---
    map_provider: str = "osm"  # "osm" | "google"
    maps_api_key: str = ""

    # --- Email (SMTP — Gmail, SendGrid's SMTP relay, SES, Outlook, etc.) ---
    # Generic SMTP, not tied to any one provider. Switching providers is a
    # .env change (SMTP_HOST/PORT/USERNAME/PASSWORD), not a code change.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "no-reply@mittendrin.in"

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()