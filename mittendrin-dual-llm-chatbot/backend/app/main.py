"""
app/main.py

FastAPI application entry point: creates the app instance, configures
CORS, and mounts the router.

Run with:
    uv run uvicorn app.main:app --reload --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import router

settings = get_settings()

logging.basicConfig(
    level="DEBUG" if settings.app_env != "production" else "INFO",
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mittendrin Events API",
    description="Backend for event discovery, registration, and SLM-assisted event drafting.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Starting Mittendrin backend (env=%s)", settings.app_env)

    primary = settings.llm_primary_provider
    fallback = "local" if primary == "claude" else "claude"
    claude_ready = bool(settings.anthropic_api_key)

    if primary == "claude" and not claude_ready:
        logger.info(
            "LLM: primary=claude but ANTHROPIC_API_KEY is unset -> using local (%s) directly, no fallback available",
            settings.local_llm_model,
        )
    else:
        logger.info(
            "LLM: primary=%s, fallback=%s (local=%s @ %s, claude=%s)",
            primary,
            fallback,
            settings.local_llm_model,
            settings.local_llm_base_url,
            "ready" if claude_ready else "not configured",
        )

    logger.info("Map provider: %s", settings.map_provider)
    logger.info(
        "Email: %s",
        f"{settings.smtp_host}:{settings.smtp_port}" if settings.smtp_username else "not configured",
    )