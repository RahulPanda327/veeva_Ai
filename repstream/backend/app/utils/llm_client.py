"""Dynamic LLM client — switch providers from .env.

One knob controls the whole app's LLM:
    LLM_PROVIDER = ollama | openai | groq
    LLM_MODEL    = model name for that provider

`make_llm_client()` returns a small OpenAI-style shim so every caller can keep
writing:

    client = make_llm_client()
    resp = client.chat.completions.create(model=settings.LLM_MODEL, messages=[...])
    text = resp.choices[0].message.content

Under the hood it builds the right LangChain chat model for LLM_PROVIDER. Add a
new provider by adding one branch in `_build_chat_model()`.

Provider packages are imported lazily, so you only need the one you use:
    ollama → langchain-ollama   openai → langchain-openai   groq → langchain-groq
"""
import logging
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config import settings

logger = logging.getLogger(__name__)


# ── Provider factory ──────────────────────────────────────────────────────────
def _build_chat_model(temperature: Optional[float], max_tokens: Optional[int], json_mode: bool):
    """Construct the LangChain chat model for the configured LLM_PROVIDER, mapping
    the common knobs (model, temperature, max tokens, JSON mode) to each provider's
    own parameter names."""
    provider = (settings.LLM_PROVIDER or "ollama").strip().lower()
    model = settings.LLM_MODEL

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        host = (settings.OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")
        if host.endswith("/v1"):  # native ollama API is at the root, not /v1
            host = host[: -len("/v1")]
        kwargs = {"model": model, "base_url": host,
                  "client_kwargs": {"timeout": settings.LLM_TIMEOUT}}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["num_predict"] = max_tokens
        if json_mode:
            kwargs["format"] = "json"
        return ChatOllama(**kwargs)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        kwargs = {"model": model, "api_key": settings.OPENAI_API_KEY,
                  "timeout": settings.LLM_TIMEOUT, "max_retries": settings.LLM_MAX_RETRIES}
        if settings.OPENAI_BASE_URL:
            kwargs["base_url"] = settings.OPENAI_BASE_URL
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        return ChatOpenAI(**kwargs)

    if provider == "groq":
        from langchain_groq import ChatGroq
        kwargs = {"model": model, "api_key": settings.GROQ_API_KEY,
                  "timeout": settings.LLM_TIMEOUT, "max_retries": settings.LLM_MAX_RETRIES}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        return ChatGroq(**kwargs)

    raise ValueError(f"Unknown LLM_PROVIDER '{provider}' — use one of: ollama, openai, groq")


# ── OpenAI-style response shim ────────────────────────────────────────────────
# The services read `resp.choices[0].message.content`; LangChain returns an
# AIMessage whose text is `.content`. These wrappers bridge the two shapes.
class _Message:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str):
        self.choices: List[_Choice] = [_Choice(content)]


def _to_lc_messages(messages: list) -> list:
    """OpenAI-style [{role, content}] → LangChain message objects."""
    out = []
    for m in messages:
        role = (m.get("role") or "user").lower()
        content = m.get("content", "")
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


class _Completions:
    """Mimics openai `client.chat.completions` but routes to LLM_PROVIDER."""

    def create(
        self,
        model: Optional[str] = None,   # ignored — the active model comes from LLM_MODEL
        messages: Optional[list] = None,
        response_format: Optional[dict] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **_ignored,
    ) -> _Response:
        json_mode = (response_format or {}).get("type") == "json_object"
        lc_messages = _to_lc_messages(messages or [])

        last_exc: Optional[Exception] = None
        for attempt in range(1, settings.LLM_MAX_RETRIES + 1):
            try:
                llm = _build_chat_model(temperature, max_tokens, json_mode)
                resp = llm.invoke(lc_messages)
                content = resp.content if isinstance(resp.content, str) else str(resp.content)
                return _Response(content)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "LLM call failed [%s] (attempt %d/%d): %s",
                    settings.LLM_PROVIDER, attempt, settings.LLM_MAX_RETRIES, exc,
                )
        raise RuntimeError(
            f"LLM call failed after {settings.LLM_MAX_RETRIES} attempts "
            f"[provider={settings.LLM_PROVIDER}, model={settings.LLM_MODEL}]: {last_exc}"
        ) from last_exc


class _Chat:
    def __init__(self):
        self.completions = _Completions()


class LLMClient:
    """Minimal OpenAI-compatible wrapper; provider chosen by LLM_PROVIDER."""

    def __init__(self):
        self.chat = _Chat()


def make_llm_client() -> LLMClient:
    """The single place the LLM provider is configured. Provider + model come from
    LLM_PROVIDER / LLM_MODEL in .env, so both can be changed by editing .env alone."""
    return LLMClient()


def normalize_str_list(value) -> list:
    """Coerce any 'list of steps/points' the model returned into List[str].

    Providers disagree on how to express a list even when the prompt is explicit.
    GPT-4o returns a newline string or a list of strings; smaller local models
    (phi4-mini) return a list of OBJECTS — [{"step_number": 1, "action": "..."}] —
    which fails a List[str] schema and 500s the whole endpoint. Every LLM-fed
    list field routes through here so the response format stays List[str] no
    matter which provider is enabled."""
    if value is None:
        return []
    if isinstance(value, str):
        return [s.strip() for s in value.split("\n") if s.strip()]
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list):
        return [str(value).strip()]

    out: list = []
    for step in value:
        if isinstance(step, str):
            text = step
        elif isinstance(step, dict):
            # Prefer the obvious text key; otherwise join the non-numeric values
            # so nothing the model wrote is silently dropped.
            text = next(
                (str(step[k]) for k in ("action", "step", "text", "description", "detail", "point")
                 if step.get(k)),
                " ".join(str(v) for v in step.values() if not isinstance(v, (int, float))),
            )
        else:
            text = str(step)
        text = text.strip()
        if text:
            out.append(text)
    return out
