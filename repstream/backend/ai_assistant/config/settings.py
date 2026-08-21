from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# One .env for the whole project, shared with the RepStream backend. Absolute
# rather than the bare ".env", which pydantic reads relative to the CURRENT
# WORKING DIRECTORY and so resolved differently depending on which application
# started the process.
#
# Found by walking UP to the nearest .env instead of a fixed parents[N], because
# the folder depth differs per deployment:
#   dev : repstream/backend/ai_assistant/config/settings.py  -> 3 levels up
#   vm  : veeva_ai_main/ai_assistant/config/settings.py      -> 2 levels up
# A missing env_file is not an error in pydantic — every setting silently falls
# back to its default, which surfaces much later as an auth or connection
# failure rather than as a missing-file error.
def _find_env_file() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return here.parents[3] / ".env"


_ENV_FILE = _find_env_file()


class AppConfig(BaseSettings):
    """
    Central blackbox — 42 runtime-tunable parameters.
    All values load from .env; mutate the cached instance at runtime
    (e.g. via POST /model/switch) to change behaviour without restart.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        case_sensitive=False,
        extra="allow",
    )

    # ── [1-3] API Keys ─────────────────────────────────────────────────────────
    groq_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # ── [4-7] Provider / Model / Scenario Selection ────────────────────────────
    active_api_provider: str = "groq"       # groq | openai | anthropic
    llm_model_name: str = "llama-3.1-8b-instant"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    active_scenario: int = 1                # 1 | 2 | 3 | 4
    use_langgraph: bool = False             # True → LangGraph + SQLite memory
    use_redis_pg: bool = False              # True → Redis window + PostgreSQL store
    redis_url: str = "redis://localhost:6379/0"
    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/chatbot"

    # ── [8-12] LLM Generation Parameters ──────────────────────────────────────
    temperature: float = 0.7
    max_tokens: int = 1024
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

    # ── [13-16] Memory & Cache ─────────────────────────────────────────────────
    memory_window_size: int = 15            # 10–20 conversation turns
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    max_cache_entries: int = 100

    # ── [17-19] Embedding Retrieval ────────────────────────────────────────────
    embedding_dimension: int = 384
    cosine_similarity_threshold: float = 0.70
    top_k_retrieval: int = 5

    # ── [20-21] Rule-Based Model ───────────────────────────────────────────────
    rule_confidence_threshold: float = 0.80
    rule_max_matches: int = 3

    # ── [22-24] JWT Authentication ─────────────────────────────────────────────
    jwt_secret_key: str = "change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # ── [25-26] Server ─────────────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # ── [27-28] Admin Credentials ──────────────────────────────────────────────
    admin_username: str = "admin"
    admin_password: str = "changeme123"

    # ── [29-32] Pinecone Vector Store ──────────────────────────────────────────
    pinecone_api_key: str = ""
    pinecone_index_name: str = "datastream-kb"
    pinecone_cloud: str = "aws"          # aws | gcp | azure
    pinecone_region: str = "us-east-1"

    # ── [33-37] Database (Scenario 4) — Azure Synapse / SQL Server ──────────────
    db_host: str = ""                    # e.g. averitassynprdwks.sql.azuresynapse.net
    db_name: str = ""                    # e.g. averitas_syn_prd_db
    db_user: str = ""
    db_password: str = ""
    db_driver: str = "{ODBC Driver 17 for SQL Server}"

    # ── [38-40] Query Safety & Limits ───────────────────────────────────────────
    db_query_timeout_seconds: int = 30
    db_max_rows: int = 1000
    db_llm_fallback_enabled: bool = True  # use LLM when no template matches

    # ── [41-42] Chart Generation ────────────────────────────────────────────────
    chart_enabled: bool = True
    chart_output_dir: str = "charts"


@lru_cache()
def get_config() -> AppConfig:
    """Returns the singleton config instance (mutable — changes persist in-process)."""
    return AppConfig()
