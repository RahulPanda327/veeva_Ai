"""OpenAI GPT-4o wrapper with retry, rate-limit handling, and Redis caching."""
import hashlib
import json
import logging
import os
import time
from typing import Optional

import openai
from openai import OpenAI

from app.config import settings
from app.utils.cache import cache_get, cache_set

_STUB_MODE = os.getenv("LLM_STUB_MODE", "false").lower() == "true"

_STUB_RESPONSES = {
    "insight": '{"insight": "Rx volume trending upward this quarter; competitor brand share declining in patient panel. High conversion potential.", "highlight": "High conversion potential."}',
    "brief": (
        "Dr. [Name] actively prescribes in the EPI space and shares a peer "
        "connection with an existing Zenpep writer — a warm introduction via that "
        "shared colleague provides a natural conversation starter. "
        "Lead with patient outcomes data and the Savings Card to address cost concerns."
    ),
}

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT)
    return _client


def _make_cache_key(prompt: str, system: str) -> str:
    payload = json.dumps({"prompt": prompt, "system": system}, sort_keys=True)
    return f"llm:{hashlib.sha256(payload.encode()).hexdigest()}"


def call_llm(
    prompt: str,
    system_message: str = "You are a pharmaceutical sales intelligence assistant.",
    cache_ttl: int = settings.CACHE_TTL_INSIGHT,
    max_tokens: int = 150,
    temperature: float = 0.3,
) -> str:
    """Call GPT-4o with caching, retries, and exponential back-off on rate limits.

    Returns the generated text string. Raises on unrecoverable errors.
    """
    if _STUB_MODE:
        stub = _STUB_RESPONSES["brief"] if "brief" in prompt.lower() or "outreach" in prompt.lower() else _STUB_RESPONSES["insight"]
        return stub

    cache_key = _make_cache_key(prompt, system_message)
    cached = cache_get(cache_key)
    if cached:
        return cached

    client = _get_client()
    last_exc: Optional[Exception] = None

    for attempt in range(1, settings.OPENAI_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = response.choices[0].message.content.strip()
            cache_set(cache_key, text, ttl=cache_ttl)
            return text

        except openai.RateLimitError as exc:
            wait = 2 ** attempt
            logger.warning("OpenAI rate limit hit (attempt %d/%d). Retrying in %ds.", attempt, settings.OPENAI_MAX_RETRIES, wait)
            time.sleep(wait)
            last_exc = exc

        except openai.APITimeoutError as exc:
            logger.warning("OpenAI timeout (attempt %d/%d).", attempt, settings.OPENAI_MAX_RETRIES)
            last_exc = exc

        except openai.OpenAIError as exc:
            logger.error("OpenAI error: %s", exc)
            raise

    raise RuntimeError(f"LLM call failed after {settings.OPENAI_MAX_RETRIES} retries: {last_exc}") from last_exc
