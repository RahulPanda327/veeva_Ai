from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from config.settings import get_config
from memory.conversation_memory import ConversationMemory
from utils.logging_util import setup_logging

if TYPE_CHECKING:
    from models.llm_client import LLMClient
    from models.embedding_model import EmbeddingModel
    from models.rule_based_model import RuleBasedModel
    from dbs.session_store import SessionStore

logger = setup_logging("service_factory")

@dataclass
class ChatRequest:
    query: str
    session_id: str
    user_id: str
    system_prompt: Optional[str] = None
    metadata_filter: Optional[dict] = None    # Pinecone metadata filter for Scenario 3
    metadata: dict = field(default_factory=dict)


@dataclass
class ChatResponse:
    response: str
    session_id: str
    scenario: int
    provider: str
    model: str
    cached: bool = False
    rule_matched: Optional[str] = None
    retrieved_docs: int = 0
    cosine_scores: list[float] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class BaseService(ABC):
    def __init__(self, memory: ConversationMemory):
        self.cfg = get_config()
        self.memory = memory

    @abstractmethod
    def chat(self, request: ChatRequest) -> ChatResponse:
        ...

    @abstractmethod
    def chat_stream(self, request: ChatRequest) -> Iterator[dict]:
        """
        Yield event dicts as the response is produced.
          {"type": "chunk", "content": "..."}     — token / fragment
          {"type": "meta",  ...ChatResponse...}    — final metadata after the last chunk
        """
        ...

    @property
    @abstractmethod
    def scenario_number(self) -> int:
        ...

    # Helper used by streaming scenarios to emit the trailing meta event
    def _meta_event(
        self,
        request: ChatRequest,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        cached: bool = False,
        rule_matched: Optional[str] = None,
        retrieved_docs: int = 0,
        cosine_scores: Optional[list[float]] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        return {
            "type": "meta",
            "session_id": request.session_id,
            "scenario": self.scenario_number,
            "provider": provider or self.cfg.active_api_provider,
            "model": model or self.cfg.llm_model_name,
            "cached": cached,
            "rule_matched": rule_matched,
            "retrieved_docs": retrieved_docs,
            "cosine_scores": cosine_scores or [],
            "metadata": metadata or {},
        }


class ServiceFactory:
    _store: Optional[SessionStore] = None
    _memory: Optional[ConversationMemory] = None
    _llm: Optional[LLMClient] = None
    _embeddings: Optional[EmbeddingModel] = None
    _rules: Optional[RuleBasedModel] = None
    _db = None
    _sql_router = None
    _charter = None

    @classmethod
    def initialize(cls):
        cfg = get_config()

        # Store must come first — memory depends on it
        if cls._store is None:
            if getattr(cfg, "use_redis_pg", False):
                from dbs.session_store_pg import SessionStorePG
                cls._store = SessionStorePG()
            else:
                from dbs.session_store import SessionStore
                cls._store = SessionStore()

        if cls._memory is None:
            if getattr(cfg, "use_redis_pg", False):
                cls._memory = ConversationMemory(store=None)
            else:
                cls._memory = ConversationMemory(store=cls._store)

        if cls._rules is None:
            from models.rule_based_model import RuleBasedModel
            cls._rules = RuleBasedModel()

        logger.info({"event": "factory_initialized"})

    @classmethod
    def get_llm(cls) -> LLMClient:
        if cls._llm is None:
            from models.llm_client import LLMClient
            cls._llm = LLMClient()
        return cls._llm

    @classmethod
    def get_embeddings(cls) -> EmbeddingModel:
        # Pinecone is persistent across restarts — never auto-seed.
        # Admins populate via POST /documents or POST /documents/seed.
        if cls._embeddings is None:
            from models.embedding_model import EmbeddingModel
            cls._embeddings = EmbeddingModel()
        return cls._embeddings

    @classmethod
    def get_db(cls):
        if cls._db is None:
            from dbs.sql_server_client import SQLServerClient
            cls._db = SQLServerClient()
        return cls._db

    @classmethod
    def get_sql_router(cls):
        if cls._sql_router is None:
            from db_qa.sql_query_router import SQLQueryRouter
            cls._sql_router = SQLQueryRouter()
        return cls._sql_router

    @classmethod
    def get_charter(cls):
        if cls._charter is None:
            from db_qa.chart_generator import ChartGenerator
            cls._charter = ChartGenerator()
        return cls._charter

    @classmethod
    def cfg_llm_fallback_enabled(cls) -> bool:
        cfg = get_config()
        return cfg.db_llm_fallback_enabled and bool(
            cfg.groq_api_key or cfg.openai_api_key or cfg.anthropic_api_key
        )

    @classmethod
    def create_langgraph(cls, scenario: int) -> BaseService:
        from services.langgraph_service import LangGraphAdapterService
        kwargs = {}
        if scenario == 4:
            kwargs["db_client"] = cls.get_db()
            kwargs["router"] = cls.get_sql_router()
            kwargs["charter"] = cls.get_charter()
        return LangGraphAdapterService(cls._memory, cls.get_llm(), **kwargs)

    @classmethod
    def create_standard(cls, scenario: int) -> BaseService:
        if scenario == 1:
            from services.scenario_1_llm import LLMOnlyService
            return LLMOnlyService(cls._memory, cls.get_llm())
        if scenario == 2:
            from services.scenario_2_llm_rules import LLMWithRulesService
            return LLMWithRulesService(
                memory=cls._memory,
                llm=cls.get_llm(),
                rules=cls._rules,
                db_client=cls.get_db(),
                router=cls.get_sql_router(),
                charter=cls.get_charter(),
            )
        if scenario == 3:
            from services.scenario_3_embedding_rules import EmbeddingRulesService
            return EmbeddingRulesService(cls._memory, cls.get_embeddings(), cls._rules)
        if scenario == 4:
            from services.scenario_4_database import DatabaseQAService
            llm = cls.get_llm() if cls.cfg_llm_fallback_enabled() else None
            return DatabaseQAService(
                memory=cls._memory,
                db_client=cls.get_db(),
                router=cls.get_sql_router(),
                charter=cls.get_charter(),
                llm=llm,
            )
        raise ValueError(f"Invalid scenario: {scenario!r}. Must be 1, 2, 3, or 4.")

    @classmethod
    def create(cls, scenario: Optional[int] = None) -> BaseService:
        cls.initialize()
        cfg = get_config()
        scenario = scenario if scenario is not None else cfg.active_scenario
        if getattr(cfg, "use_langgraph", False) and scenario in (1, 4):
            return cls.create_langgraph(scenario)
        return cls.create_standard(scenario)
