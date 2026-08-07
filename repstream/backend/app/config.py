"""RepStream configuration — loaded from environment variables."""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database — Azure Synapse Analytics (SQL Server)
    DB_HOST: str = "ds-hub-syn-wks.sql.azuresynapse.net"
    DB_PORT: int = 1433
    DB_NAME: str = "ds_hub_syndb"
    DB_USER: str = "hub_ds_ai_usr"
    DB_PASSWORD: str = ""
    HUB_SCHEMA: str = "hub_insight360"
    DS_SCHEMA: str = "ds_hub_syndb"

    # ── LLM providers ────────────────────────────────────────────────────────
    # Two providers, each keeping its OWN model / api_key / base_url. Both stay
    # configured; the *_ENABLED flag picks which one runs. Set exactly one to
    # true — if both are true Ollama wins, if neither is true OpenAI is used.
    #
    # Both speak the OpenAI-compatible chat-completions API, so a single OpenAI()
    # client serves either — only these three values change. Application code
    # must read LLM_PROVIDER / LLM_API_KEY / LLM_BASE_URL / LLM_MODEL below,
    # never a provider-prefixed name, so switching provider touches only .env.

    # Ollama — talks straight to the daemon; needs the OpenAI-compatible /v1 path
    # (the bare host is the native API, which this client does not speak).
    OLLAMA_ENABLED: bool = False
    OLLAMA_MODEL: str = "phi4-mini"
    OLLAMA_API_KEY: str = "ollama"   # daemon needs no auth; SDK just rejects an empty string
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

    # OpenAI — or any OpenAI-compatible gateway.
    # An empty base_url means the SDK's own default, api.openai.com; sending a
    # gateway key there is what produces "401 Incorrect API key provided".
    OPENAI_ENABLED: bool = True
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""

    # Shared by whichever provider is active
    LLM_MAX_RETRIES: int = 3
    LLM_TIMEOUT: int = 120

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_INSIGHT: int = 86400      # 24 h
    CACHE_TTL_APPROACH_BRIEF: int = 3600  # 1 h
    CACHE_TTL_DEFAULT: int = 3600

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:4200","http://localhost:8004",]

    # Business rules
    RX_TREND_HIGH_THRESHOLD: float = 15.0
    RX_TREND_LOW_THRESHOLD: float = -10.0
    RX_HIGH_PERCENTILE: float = 75.0
    WEEKLY_TARGET_RATIO: float = 0.65

    OBJECTION_HIGH_THRESHOLD: int = 8
    OBJECTION_MEDIUM_MIN: int = 3
    OBJECTION_SUCCESS_WINDOW_DAYS: int = 30

    # Target ICD-10 codes for Module 2
    TARGET_ICD10_CODES: List[str] = [
        "K86.1",   # Other chronic pancreatitis
        "K86.81",  # Exocrine pancreatic insufficiency
        "K31.1",   # Adult hypertrophic pyloric stenosis
        "K86.89",  # Other specified diseases of pancreas
        "K90.3",   # Pancreatic steatorrhoea
        "C25.0",   # Malignant neoplasm of head of pancreas
        "C25.9",   # Malignant neoplasm of pancreas, unspecified
        "K86.0",   # Alcohol-induced chronic pancreatitis
    ]

    # Dev flags
    DEV_SKIP_AUTH: bool = False
    LLM_STUB_MODE: bool = False

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Active-provider resolution ───────────────────────────────────────────
    # The single place that decides which provider's values are live. Everything
    # else reads the four LLM_* properties below, so no service ever names a
    # provider — flipping a *_ENABLED flag in .env is the whole switch.
    @property
    def _active_llm(self) -> tuple:
        """(provider, api_key, base_url, model) for the first enabled provider."""
        for provider, enabled, key, url, model in (
            ("ollama", self.OLLAMA_ENABLED, self.OLLAMA_API_KEY, self.OLLAMA_BASE_URL, self.OLLAMA_MODEL),
            ("openai", self.OPENAI_ENABLED, self.OPENAI_API_KEY, self.OPENAI_BASE_URL, self.OPENAI_MODEL),
        ):
            if enabled:
                return provider, key, url, model
        # Nothing enabled — fall back to OpenAI rather than failing at call time.
        return "openai", self.OPENAI_API_KEY, self.OPENAI_BASE_URL, self.OPENAI_MODEL

    @property
    def LLM_PROVIDER(self) -> str:
        return self._active_llm[0]

    @property
    def LLM_API_KEY(self) -> str:
        """Ollama needs no auth, but the OpenAI SDK refuses an empty api_key —
        so an unset key becomes a harmless placeholder. A provider that really
        does need a key still fails loudly with its own 401."""
        return self._active_llm[1] or "not-needed"

    @property
    def LLM_BASE_URL(self) -> str:
        """The OpenAI-compatible path, with /v1 appended when it is missing.

        Ollama's own docs and client use the bare host (http://host:11434) —
        that is the NATIVE API. This client speaks the OpenAI-compatible one at
        /v1, so the bare host would 404. Normalising here means .env can carry
        either form. Empty stays empty: that means "use the SDK's own default".
        """
        url = self._active_llm[2].strip().rstrip("/")
        if url and not url.endswith("/v1"):
            url += "/v1"
        return url

    @property
    def LLM_MODEL(self) -> str:
        return self._active_llm[3]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
