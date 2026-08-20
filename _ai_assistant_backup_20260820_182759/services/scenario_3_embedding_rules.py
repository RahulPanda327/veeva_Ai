from collections.abc import Iterator

from services.base_service import BaseService, ChatRequest, ChatResponse
from models.embedding_model import EmbeddingModel
from models.rule_based_model import RuleBasedModel
from memory.conversation_memory import ConversationMemory
from utils.logging_util import setup_logging

logger = setup_logging("scenario_3_embedding_rules")

_NO_RESULT_MSG = (
    "I don't have specific information on that topic in my knowledge base.\n\n"
    "**I can help you with:**\n"
    "• 📂 **Data pipeline questions** — file schedules, load history, failures, row counts\n"
    "• 🔧 **Support** — password reset, error troubleshooting, API rate limits\n"
    "• 💰 **Pricing & plans** — subscription tiers and billing\n"
    "• 🔄 **Model/scenario switching** — change AI mode at runtime\n\n"
    "Try asking: *'Which files failed yesterday?'* or *'What is the pricing?'*\n"
    "Or switch to **Scenario 1** (LLM mode) for general questions."
)

class EmbeddingRulesService(BaseService):
    """
    Scenario 3 — Semantic retrieval + rules. No cloud LLM required.
    Flow: cache → rule match + cosine retrieval (parallel) → compose response.

    Priority: rule with high confidence > retrieved docs > fallback message.
    When both match, the rule answer is given first followed by relevant context.
    """

    def __init__(
        self,
        memory: ConversationMemory,
        embeddings: EmbeddingModel,
        rules: RuleBasedModel,
    ):
        super().__init__(memory)
        self.embeddings = embeddings
        self.rules = rules

    @property
    def scenario_number(self) -> int:
        return 3

    def _build_retrieval_query(self, request: ChatRequest) -> str:
        context = self.memory.get_context(request.session_id)
        # Find the most recent prior user message (before this turn)
        prior_user = next(
            (m["content"] for m in reversed(context) if m["role"] == "user"),
            None,
        )
        if prior_user and prior_user.strip().lower() != request.query.strip().lower():
            return f"{prior_user} {request.query}"
        return request.query

    def chat(self, request: ChatRequest) -> ChatResponse:
        # Retrieval responses are context-independent — cache is safe.
        cached = self.memory.get_cached(request.query, self.scenario_number, "local")
        if cached:
            # Still record the turn so history stays complete.
            self.memory.add_message(request.session_id, "user", request.query)
            self.memory.add_message(request.session_id, "assistant", cached)
            return ChatResponse(
                response=cached,
                session_id=request.session_id,
                scenario=self.scenario_number,
                provider="local",
                model=self.cfg.embedding_model_name,
                cached=True,
            )

        rule_match = self.rules.get_best_match(request.query)
        
        retrieval_query = self._build_retrieval_query(request)
        retrieved = self.embeddings.retrieve(
            retrieval_query,
            filter=request.metadata_filter,
        )
        cosine_scores = [r.similarity for r in retrieved]

        logger.info({
            "event": "embedding_retrieval",
            "query_preview": request.query[:60],
            "enriched": retrieval_query != request.query,
            "metadata_filter": request.metadata_filter,
            "docs_retrieved": len(retrieved),
            "top_cosine": round(cosine_scores[0], 4) if cosine_scores else None,
            "rule_intent": rule_match.rule.intent if rule_match else None,
        })

        rule_confident = (
            rule_match is not None
            and rule_match.confidence >= self.cfg.rule_confidence_threshold
        )

        if rule_confident and retrieved:
            context = self.embeddings.format_context(retrieved[:2])
            response_text = f"{rule_match.rule.response}\n\nAdditional context:\n{context}"
        elif rule_confident:
            response_text = rule_match.rule.response
        elif retrieved:
            context = self.embeddings.format_context(retrieved)
            response_text = f"Based on available information:\n\n{context}"
        else:
            response_text = _NO_RESULT_MSG

        self.memory.add_message(request.session_id, "user", request.query)
        self.memory.add_message(request.session_id, "assistant", response_text)
        self.memory.set_cached(request.query, self.scenario_number, "local", response_text)

        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            scenario=self.scenario_number,
            provider="local",
            model=self.cfg.embedding_model_name,
            rule_matched=rule_match.rule.intent if rule_confident else None,
            retrieved_docs=len(retrieved),
            cosine_scores=cosine_scores,
        )

    def chat_stream(self, request: ChatRequest) -> Iterator[dict]:
        # Scenario 3 has no LLM, so the response is built synchronously and
        # yielded as a single chunk for protocol consistency.
        result = self.chat(request)
        yield {"type": "chunk", "content": result.response}
        yield self._meta_event(
            request,
            provider="local",
            model=self.cfg.embedding_model_name,
            cached=result.cached,
            rule_matched=result.rule_matched,
            retrieved_docs=result.retrieved_docs,
            cosine_scores=result.cosine_scores,
        )
