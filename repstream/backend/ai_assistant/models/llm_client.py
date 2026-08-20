from collections.abc import Iterator
from typing import Optional

from config.settings import get_config
from utils.logging_util import setup_logging

logger = setup_logging("llm_client")

# Maps provider → default first-choice model
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "groq": "llama-3.1-8b-instant",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}


class LLMClient:
    """
    Unified LLM client supporting Groq, OpenAI, and Anthropic.
    Clients are instantiated lazily; switch provider at runtime via switch_provider().
    """

    def __init__(self, provider: Optional[str] = None):
        self.cfg = get_config()
        self.provider = provider or self.cfg.active_api_provider
        self._clients: dict[str, object] = {}

    # ── Lazy client accessors ───────────────────────────────────────────────────

    def _groq(self):
        if "groq" not in self._clients:
            from groq import Groq
            self._clients["groq"] = Groq(api_key=self.cfg.groq_api_key)
        return self._clients["groq"]

    def _openai(self):
        if "openai" not in self._clients:
            from openai import OpenAI
            self._clients["openai"] = OpenAI(api_key=self.cfg.openai_api_key)
        return self._clients["openai"]

    def _anthropic(self):
        if "anthropic" not in self._clients:
            import anthropic
            self._clients["anthropic"] = anthropic.Anthropic(
                api_key=self.cfg.anthropic_api_key
            )
        return self._clients["anthropic"]

    # ── Public interface ────────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> str:
        provider = provider or self.cfg.active_api_provider
        model = model or self.cfg.llm_model_name
        temperature = temperature if temperature is not None else self.cfg.temperature
        max_tokens = max_tokens or self.cfg.max_tokens
        top_p = top_p if top_p is not None else self.cfg.top_p

        logger.info({
            "event": "llm_request",
            "provider": provider,
            "model": model,
            "messages": len(messages),
        })

        try:
            if provider == "groq":
                return self._chat_groq(messages, model, temperature, max_tokens, top_p)
            elif provider == "openai":
                return self._chat_openai(messages, model, temperature, max_tokens, top_p)
            elif provider == "anthropic":
                return self._chat_anthropic(messages, model, temperature, max_tokens)
            else:
                raise ValueError(f"Unsupported provider: {provider!r}")
        except Exception as exc:
            logger.error({"event": "llm_error", "provider": provider, "error": str(exc)})
            raise

    def chat_stream(
        self,
        messages: list[dict],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> Iterator[str]:
        """Yield response text chunks as they arrive from the LLM."""
        provider = provider or self.cfg.active_api_provider
        model = model or self.cfg.llm_model_name
        temperature = temperature if temperature is not None else self.cfg.temperature
        max_tokens = max_tokens or self.cfg.max_tokens
        top_p = top_p if top_p is not None else self.cfg.top_p

        logger.info({
            "event": "llm_stream_start",
            "provider": provider,
            "model": model,
        })

        try:
            if provider == "groq":
                yield from self._stream_openai_compatible(self._groq(), messages, model, temperature, max_tokens, top_p)
            elif provider == "openai":
                yield from self._stream_openai_compatible(self._openai(), messages, model, temperature, max_tokens, top_p)
            elif provider == "anthropic":
                yield from self._stream_anthropic(messages, model, temperature, max_tokens)
            else:
                raise ValueError(f"Unsupported provider: {provider!r}")
        except Exception as exc:
            logger.error({"event": "llm_stream_error", "provider": provider, "error": str(exc)})
            raise

    def _stream_openai_compatible(self, client, messages, model, temperature, max_tokens, top_p) -> Iterator[str]:
        """Groq and OpenAI share the same chat-completions streaming protocol."""
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=self.cfg.frequency_penalty,
            presence_penalty=self.cfg.presence_penalty,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    def _stream_anthropic(self, messages, model, temperature, max_tokens) -> Iterator[str]:
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_messages = [m for m in messages if m["role"] != "system"]
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        with self._anthropic().messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    def switch_provider(self, provider: str, model: Optional[str] = None):
        if provider not in PROVIDER_DEFAULT_MODELS:
            raise ValueError(f"Unknown provider: {provider!r}")
        self.cfg.active_api_provider = provider
        self.cfg.llm_model_name = model or PROVIDER_DEFAULT_MODELS[provider]
        self.provider = provider
        logger.info({"event": "provider_switched", "provider": provider, "model": self.cfg.llm_model_name})

    # ── Provider-specific implementations ──────────────────────────────────────

    def _chat_groq(self, messages, model, temperature, max_tokens, top_p) -> str:
        response = self._groq().chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=self.cfg.frequency_penalty,
            presence_penalty=self.cfg.presence_penalty,
        )
        return response.choices[0].message.content

    def _chat_openai(self, messages, model, temperature, max_tokens, top_p) -> str:
        response = self._openai().chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=self.cfg.frequency_penalty,
            presence_penalty=self.cfg.presence_penalty,
        )
        return response.choices[0].message.content

    def _chat_anthropic(self, messages, model, temperature, max_tokens) -> str:
        system_msg = next(
            (m["content"] for m in messages if m["role"] == "system"), None
        )
        user_messages = [m for m in messages if m["role"] != "system"]
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        response = self._anthropic().messages.create(**kwargs)
        return response.content[0].text
