"""RepStream configuration — loaded from environment variables."""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# One .env for the whole project, at the repstream root — shared with the
# ai_assistant chatbot. Resolved as an absolute path rather than the bare ".env",
# which pydantic reads relative to the CURRENT WORKING DIRECTORY: that silently
# picked up a different file (or none) depending on where the process was
# started from.
#   this file: repstream/backend/app/config.py
# parents[0]=app, parents[1]=backend, parents[2]=repstream.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    # Database — Azure Synapse Analytics (SQL Server)
    DB_HOST: str = "ds-hub-syn-wks.sql.azuresynapse.net"
    DB_PORT: int = 1433
    DB_NAME: str = "ds_hub_syndb"
    DB_USER: str = "hub_ds_ai_usr"
    DB_PASSWORD: str = ""
    HUB_SCHEMA: str = "hub_insight360"
    DS_SCHEMA: str = "ds_hub_syndb"

    # ── LLM providers (enable ONE with true) ──────────────────────────────────
    # Keep all three configured; flip exactly one *_ENABLED to true to pick which
    # one runs. If several are true, the first in this order wins: ollama → openai
    # → groq. Each provider keeps its OWN model name + credentials.
    OLLAMA_ENABLED: bool = True
    OPENAI_ENABLED: bool = False
    GROQ_ENABLED: bool = False

    # Ollama (local)
    OLLAMA_MODEL: str = "mistral:latest"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # OpenAI
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""   # optional: OpenAI-compatible gateway base URL

    # Groq
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_API_KEY: str = ""

    # Shared knobs
    LLM_TIMEOUT: int = 120
    LLM_MAX_RETRIES: int = 3

    def active_llm(self) -> tuple[str, str]:
        """Resolve (provider, model) from the *_ENABLED flags. First enabled in
        priority order wins; falls back to Ollama if none are enabled."""
        for provider, enabled, model in (
            ("ollama", self.OLLAMA_ENABLED, self.OLLAMA_MODEL),
            ("openai", self.OPENAI_ENABLED, self.OPENAI_MODEL),
            ("groq",   self.GROQ_ENABLED,   self.GROQ_MODEL),
        ):
            if enabled:
                return provider, model
        return "ollama", self.OLLAMA_MODEL

    @property
    def LLM_PROVIDER(self) -> str:
        return self.active_llm()[0]

    @property
    def LLM_MODEL(self) -> str:
        return self.active_llm()[1]

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
