from typing import Annotated, TypedDict, List, Optional
from collections.abc import Iterator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END

from services.base_service import BaseService, ChatRequest, ChatResponse
from services.scenario_4_database import DatabaseQAService
from config.settings import get_config
from utils.logging_util import setup_logging

logger = setup_logging("langgraph_service")


class ChatbotState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    scenario: int
    metadata: Optional[dict]


_SYSTEM_PROMPT = (
    "You are DataStream, a helpful and knowledgeable AI assistant. "
    "Provide accurate, concise, and friendly responses. "
    "If you don't know something, say so honestly."
)


class DummyMemory:
    """Passed to sub-services so they don't double-write to the store."""
    def add_message(self, session_id: str, role: str, content: str):
        pass

    def get_messages_for_llm(self, session_id: str, system_prompt: Optional[str] = None):
        return []


def build_graph(llm, db_client=None, router=None, charter=None):

    def determine_scenario(state: ChatbotState) -> str:
        return "db_qa_node" if state.get("scenario", 1) == 4 else "llm_node"

    def llm_node(state: ChatbotState) -> ChatbotState:
        messages_for_llm = [{"role": "system", "content": _SYSTEM_PROMPT}]
        for msg in state["messages"]:
            if isinstance(msg, HumanMessage) or getattr(msg, "type", None) == "human":
                messages_for_llm.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage) or getattr(msg, "type", None) == "ai":
                messages_for_llm.append({"role": "assistant", "content": msg.content})
        response_text = llm.chat(messages_for_llm)
        return {"messages": [AIMessage(content=response_text)], "metadata": {}}

    def db_qa_node(state: ChatbotState) -> ChatbotState:
        query = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage) or getattr(msg, "type", None) == "human":
                query = msg.content
                break

        db_service = DatabaseQAService(
            memory=DummyMemory(),
            db_client=db_client,
            router=router,
            charter=charter,
            llm=llm,
        )
        req = ChatRequest(query=query, session_id="langgraph_internal", user_id="user")
        response = db_service.chat(req)
        return {
            "messages": [AIMessage(content=response.response)],
            "metadata": response.metadata,
        }

    builder = StateGraph(ChatbotState)
    builder.add_node("llm_node", llm_node)
    builder.add_node("db_qa_node", db_qa_node)
    builder.add_conditional_edges(START, determine_scenario)
    builder.add_edge("llm_node", END)
    builder.add_edge("db_qa_node", END)
    return builder.compile()


class LangGraphAdapterService(BaseService):
    """
    Routes chat requests through a LangGraph state machine.
    Conversation history is loaded from the session store on each call.
    """

    def __init__(self, memory, llm, db_client=None, router=None, charter=None):
        super().__init__(memory=memory)
        self.llm = llm
        self.db_client = db_client
        self.router = router
        self.charter = charter
        self.app = build_graph(llm, db_client, router, charter)
        self.cfg = get_config()
        self._current_scenario = 1

    @property
    def scenario_number(self) -> int:
        return self._current_scenario

    def chat(self, request: ChatRequest) -> ChatResponse:
        logger.info({"event": "langgraph_chat_start", "session_id": request.session_id})
        self._current_scenario = self.cfg.active_scenario

        # Hydrate history from store
        store = getattr(self.memory, "_store", None)
        history_msgs: list[BaseMessage] = []
        if store:
            try:
                for msg in store.get_messages(request.session_id):
                    if msg.role == "user":
                        history_msgs.append(HumanMessage(content=msg.content))
                    elif msg.role in ("assistant", "ai"):
                        history_msgs.append(AIMessage(content=msg.content))
            except AttributeError:
                pass

        history_msgs.append(HumanMessage(content=request.query))

        result = self.app.invoke({
            "messages": history_msgs,
            "scenario": self._current_scenario,
        })

        response_text = result["messages"][-1].content
        metadata = result.get("metadata", {})

        # Persist turn to memory
        self.memory.add_message(request.session_id, "user", request.query)
        self.memory.add_message(request.session_id, "assistant", response_text)

        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            scenario=self._current_scenario,
            provider="db" if self._current_scenario == 4 else self.cfg.active_api_provider,
            model=f"synapse:{self.cfg.db_name}" if self._current_scenario == 4 else self.cfg.llm_model_name,
            metadata=metadata,
        )

    def chat_stream(self, request: ChatRequest) -> Iterator[dict]:
        response = self.chat(request)
        yield {"type": "chunk", "content": response.response}
        yield self._meta_event(
            request,
            provider=response.provider,
            model=response.model,
            metadata=response.metadata,
        )
