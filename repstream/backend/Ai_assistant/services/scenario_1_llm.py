from collections.abc import Iterator

from services.base_service import BaseService, ChatRequest, ChatResponse
from models.llm_client import LLMClient
from memory.conversation_memory import ConversationMemory
from utils.logging_util import setup_logging

logger = setup_logging("scenario_1_llm")

_SYSTEM_PROMPT = (
    "You are DataStream, a helpful and knowledgeable AI assistant. "
    "Provide accurate, concise, and friendly responses. "
    "If you don't know something, say so honestly."
)


class LLMOnlyService(BaseService):
    """
    Scenario 1 — Pure LLM.
    Flow: cache check → build context from memory → call LLM → store result.
    """

    def __init__(self, memory: ConversationMemory, llm: LLMClient):
        super().__init__(memory)
        self.llm = llm

    @property
    def scenario_number(self) -> int:
        return 1

    def chat(self, request: ChatRequest) -> ChatResponse:
        provider = self.cfg.active_api_provider

        # Always record the user message first so memory stays complete.
        # LLM responses are context-dependent and not cached — the same question
        # in different conversation states should produce different answers.
        self.memory.add_message(request.session_id, "user", request.query)
        messages = self.memory.get_messages_for_llm(
            request.session_id,
            system_prompt=request.system_prompt or _SYSTEM_PROMPT,
        )

        logger.info({
            "event": "llm_call",
            "scenario": 1,
            "provider": provider,
            "session": request.session_id,
            "context_turns": len(messages),
        })

        response_text = self.llm.chat(messages)

        self.memory.add_message(request.session_id, "assistant", response_text)

        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            scenario=self.scenario_number,
            provider=provider,
            model=self.cfg.llm_model_name,
        )

    def chat_stream(self, request: ChatRequest) -> Iterator[dict]:
        provider = self.cfg.active_api_provider
        self.memory.add_message(request.session_id, "user", request.query)
        messages = self.memory.get_messages_for_llm(
            request.session_id,
            system_prompt=request.system_prompt or _SYSTEM_PROMPT,
        )

        logger.info({
            "event": "llm_stream",
            "scenario": 1,
            "provider": provider,
            "session": request.session_id,
            "context_turns": len(messages),
        })

        buffer: list[str] = []
        for chunk in self.llm.chat_stream(messages):
            buffer.append(chunk)
            yield {"type": "chunk", "content": chunk}

        response_text = "".join(buffer)
        self.memory.add_message(request.session_id, "assistant", response_text)
        yield self._meta_event(request, provider=provider)
