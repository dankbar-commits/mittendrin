"""
app/clients/llm_client.py

Talks to two possible providers: any OpenAI-compatible local server (LM
Studio, Ollama, vLLM, etc. — configured via LOCAL_LLM_BASE_URL /
LOCAL_LLM_MODEL / LOCAL_LLM_API_KEY) and Claude directly (anthropic_client.py).

Which one is tried first is controlled by LLM_PRIMARY_PROVIDER ("claude" or
"local") in .env — whichever is NOT primary becomes the automatic fallback
if the primary fails or times out. No code change needed to switch order or
to switch local providers, only .env.

Nothing else in the app should call a model provider directly — everything
goes through chat_completion() / chat_completion_json() here.
"""

import asyncio
import json
import logging

import httpx

from app.clients import anthropic_client
from app.clients.anthropic_client import AnthropicError
from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the primary provider fails AND the fallback (if
    configured/available) also failed."""


async def _call_local(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    enable_thinking: bool,
) -> str:
    """Calls the local OpenAI-compatible server directly, no fallback logic."""
    settings = get_settings()

    payload = {
        "model": settings.local_llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Nemotron-specific reasoning toggle; harmless no-op on models/servers
        # that don't recognize it (Ollama, vLLM, etc. just ignore extra fields).
        "enable_thinking": enable_thinking,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.local_llm_timeout_seconds) as client:
            response = await client.post(
                f"{settings.local_llm_base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.local_llm_api_key}"},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        raise LLMError(f"Local LLM returned {e.response.status_code}: {e.response.text}") from e
    except httpx.RequestError as e:
        raise LLMError(f"Could not reach local LLM at {settings.local_llm_base_url}: {e}") from e

    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message", {})
    content = message.get("content")

    # Some reasoning-capable models put the final answer in a separate
    # field when thinking is on, leaving `content` empty.
    if not content and message.get("reasoning_content"):
        content = message["reasoning_content"]

    if not content or not content.strip():
        raise LLMError(
            f"Local LLM returned empty content (finish_reason: {choice.get('finish_reason', 'unknown')})"
        )

    return content


async def _call_local_with_timeout(
    messages: list[dict[str, str]], temperature: float, max_tokens: int, enable_thinking: bool
) -> str:
    settings = get_settings()
    return await asyncio.wait_for(
        _call_local(messages, temperature, max_tokens, enable_thinking),
        timeout=settings.local_llm_timeout_seconds,
    )


async def _call_claude(messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
    try:
        return await anthropic_client.chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
    except AnthropicError as e:
        raise LLMError(f"Claude call failed: {e}") from e


async def chat_completion(
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 512,
    enable_thinking: bool = False,
) -> str:
    """
    Tries settings.llm_primary_provider first; on failure or timeout, falls
    back to the other provider automatically. If the primary is "claude"
    but ANTHROPIC_API_KEY isn't set, skips straight to local rather than
    failing immediately — same idea in reverse isn't needed since local
    has no equivalent "not configured" state (it always has some base_url).
    """
    settings = get_settings()
    primary_is_claude = settings.llm_primary_provider == "claude"

    async def call_local() -> str:
        return await _call_local_with_timeout(messages, temperature, max_tokens, enable_thinking)

    async def call_claude() -> str:
        return await _call_claude(messages, temperature, max_tokens)

    if primary_is_claude:
        primary, primary_name = call_claude, "Claude"
        fallback, fallback_name = call_local, "local LLM"
    else:
        primary, primary_name = call_local, "local LLM"
        fallback, fallback_name = call_claude, "Claude"

    # If Claude is primary but not actually configured, don't even attempt
    # it — go straight to local instead of guaranteeing a failure first.
    # Still needs its own error handling: a raw TimeoutError here would
    # otherwise crash through as an unhandled 500 instead of a clean
    # {ok: false, error} response.
    if primary_is_claude and not settings.anthropic_api_key:
        logger.warning("Primary provider is Claude but ANTHROPIC_API_KEY is unset — using local LLM directly")
        try:
            return await call_local()
        except (LLMError, TimeoutError) as local_error:
            raise LLMError(f"Local LLM failed and no Claude fallback configured: {local_error}") from local_error

    try:
        return await primary()
    except (LLMError, TimeoutError) as primary_error:
        logger.warning("%s failed or timed out, falling back to %s: %s", primary_name, fallback_name, primary_error)

        if fallback_name == "Claude" and not settings.anthropic_api_key:
            raise LLMError(
                f"{primary_name} failed and no Claude fallback configured: {primary_error}"
            ) from primary_error

        try:
            return await fallback()
        except (LLMError, TimeoutError) as fallback_error:
            raise LLMError(
                f"{primary_name} failed ({primary_error}) and {fallback_name} fallback also failed ({fallback_error})"
            ) from fallback_error


async def chat_completion_json(
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 400,
    enable_thinking: bool = False,
) -> dict:
    """
    Convenience wrapper for prompts that expect a JSON object back.
    Strips markdown code fences defensively, since small models often wrap
    JSON in ```json ... ``` even when told not to.
    """
    raw = await chat_completion(
        messages, temperature=temperature, max_tokens=max_tokens, enable_thinking=enable_thinking
    )
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMError(f"Failed to parse JSON from LLM response: {raw!r}") from e