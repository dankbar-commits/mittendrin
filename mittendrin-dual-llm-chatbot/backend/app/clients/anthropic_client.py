"""
app/clients/anthropic_client.py

Fallback LLM client: calls Anthropic's Messages API directly. This is only
ever called from llm_client.py's chat_completion() when the primary local
provider (LM Studio, Ollama, etc.) is unreachable or times out — nothing
else should import this directly, so the fallback logic stays in one place.
"""

import httpx

from app.config import get_settings

ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicError(Exception):
    """Raised when the Claude fallback call fails or returns something unusable."""


async def chat_completion(
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> str:
    """
    Sends a chat completion request to Claude. Accepts the same
    OpenAI-style messages list llm_client.py uses (including an optional
    leading system message) and adapts it to Anthropic's shape, where the
    system prompt is a separate top-level field, not a message role.
    """
    settings = get_settings()

    if not settings.anthropic_api_key:
        raise AnthropicError("ANTHROPIC_API_KEY is not set — Claude fallback unavailable")

    system_parts = []
    chat_messages = []
    for m in messages:
        if m["role"] == "system":
            system_parts.append(m["content"])
        else:
            chat_messages.append(m)

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": chat_messages,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                ANTHROPIC_BASE_URL,
                json=payload,
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        raise AnthropicError(f"Anthropic API returned {e.response.status_code}: {e.response.text}") from e
    except httpx.RequestError as e:
        raise AnthropicError(f"Could not reach Anthropic API: {e}") from e

    content_blocks = data.get("content", [])
    text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")

    if not text.strip():
        raise AnthropicError("Anthropic API returned empty content")

    return text