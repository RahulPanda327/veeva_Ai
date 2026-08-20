from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from config.settings import get_config
from utils.logging_util import setup_logging

logger = setup_logging("rule_based")


@dataclass
class Rule:
    id: str
    intent: str
    keywords: list[str]
    patterns: list[str]
    response: str
    confidence: float = 1.0
    category: str = "general"
    priority: int = 0


@dataclass
class RuleMatch:
    rule: Rule
    confidence: float
    matched_keyword: Optional[str] = None
    matched_pattern: Optional[str] = None


class RuleBasedModel:
    """
    Keyword + regex rule engine.
    Pattern matches score at full rule confidence; keyword matches score proportionally.
    Rules with priority > 0 are checked before lower-priority ones.
    """

    def __init__(self, rules: Optional[list[Rule]] = None):
        self.cfg = get_config()
        self.rules: list[Rule] = sorted(
            rules or DEFAULT_RULES,
            key=lambda r: r.priority,
            reverse=True,
        )
        logger.info({"event": "rules_loaded", "count": len(self.rules)})

    def add_rule(self, rule: Rule):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def match(self, query: str) -> list[RuleMatch]:
        """Return all rules that match the query, sorted by (priority, confidence) desc."""
        q = query.lower().strip()
        matches: list[RuleMatch] = []

        for rule in self.rules:
            best: Optional[RuleMatch] = None

            for pattern in rule.patterns:
                if re.search(pattern, q, re.IGNORECASE):
                    if best is None or rule.confidence > best.confidence:
                        best = RuleMatch(
                            rule=rule,
                            confidence=rule.confidence,
                            matched_pattern=pattern,
                        )

            if best is None:
                hits = [kw for kw in rule.keywords if kw in q]
                if hits:
                    kw_conf = min(rule.confidence, (len(hits) / len(rule.keywords)) * rule.confidence)
                    best = RuleMatch(
                        rule=rule,
                        confidence=kw_conf,
                        matched_keyword=", ".join(hits),
                    )

            if best and best.confidence >= self.cfg.rule_confidence_threshold:
                matches.append(best)

        matches.sort(key=lambda m: (m.rule.priority, m.confidence), reverse=True)
        return matches[: self.cfg.rule_max_matches]

    def get_best_match(self, query: str) -> Optional[RuleMatch]:
        results = self.match(query)
        return results[0] if results else None


# ── Default rule set ─────────────────────────────────────────────────────────────

DEFAULT_RULES: list[Rule] = [
    Rule(
        id="rule_greeting",
        intent="greeting",
        keywords=["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"],
        patterns=[r"^(hi|hey|hello|howdy|greetings)\b", r"\bgood\s+(morning|afternoon|evening|day)\b"],
        response="Hello! I'm the DataStream AI assistant. How can I help you today?",
        confidence=0.95,
        category="social",
        priority=5,
    ),
    Rule(
        id="rule_farewell",
        intent="farewell",
        keywords=["bye", "goodbye", "see you", "farewell", "exit", "quit"],
        patterns=[r"\b(bye|goodbye|farewell|see\s+you|take\s+care)\b"],
        response="Goodbye! Have a great day. Feel free to come back anytime.",
        confidence=0.95,
        category="social",
        priority=5,
    ),
    Rule(
        id="rule_thanks",
        intent="thanks",
        keywords=["thank", "thanks", "thank you", "appreciate", "grateful"],
        patterns=[r"\b(thank(s|\s+you)?|appreciate|grateful)\b"],
        response="You're welcome! Is there anything else I can help you with?",
        confidence=0.90,
        category="social",
        priority=4,
    ),
    Rule(
        id="rule_help",
        intent="help_request",
        keywords=["help", "assist", "support", "how to", "can you"],
        patterns=[r"\b(help|assist|support)\b", r"\bhow\s+(do|can|should)\s+i\b"],
        response="I'm here to help! Please describe what you need and I'll guide you.",
        confidence=0.80,
        category="support",
        priority=3,
    ),
    Rule(
        id="rule_pricing",
        intent="pricing_inquiry",
        keywords=["price", "pricing", "cost", "plan", "subscription", "billing", "free tier"],
        patterns=[r"\b(price|pricing|cost|how\s+much|billing|subscription|plan)\b"],
        response=(
            "Our pricing plans:\n"
            "• Free — 100 msgs/day\n"
            "• Standard — $29/month, 5,000 msgs\n"
            "• Enterprise — $199/month, unlimited msgs + priority support"
        ),
        confidence=0.92,
        category="sales",
        priority=6,
    ),
    Rule(
        id="rule_password",
        intent="password_reset",
        keywords=["password", "reset", "forgot", "login issue", "can't login", "account access"],
        patterns=[r"(forgot|reset|change)\s+(my\s+)?password", r"can'?t\s+(log|sign)\s+in"],
        response=(
            "To reset your password:\n"
            "1. Go to Settings > Security > Change Password, or\n"
            "2. Use the Forgot Password link on the login page."
        ),
        confidence=0.95,
        category="support",
        priority=7,
    ),
    Rule(
        id="rule_api_limits",
        intent="api_rate_limits",
        keywords=["rate limit", "api limit", "too many requests", "quota", "429"],
        patterns=[r"rate\s+limit", r"api\s+(limit|quota)", r"too\s+many\s+requests", r"\b429\b"],
        response=(
            "Rate limits:\n"
            "• Standard plan: 60 requests/minute\n"
            "• Enterprise plan: 300 requests/minute\n"
            "If you're hitting limits, implement request queuing or consider upgrading."
        ),
        confidence=0.92,
        category="technical",
        priority=6,
    ),
    Rule(
        id="rule_error",
        intent="error_report",
        keywords=["error", "bug", "issue", "not working", "broken", "failed", "crash"],
        # NOTE: 'fail' intentionally excluded from pattern — keyword-only so data queries
        # like 'which files failed yesterday' get low confidence and fall through to embeddings.
        patterns=[r"\b(error|bug|broken|crash)\b", r"(not|isn'?t)\s+work(ing)?"],
        response=(
            "I'm sorry you're experiencing an issue. "
            "Please share the full error message or error code and I'll help you troubleshoot."
        ),
        confidence=0.85,
        category="support",
        priority=5,
    ),
    Rule(
        id="rule_model_switch",
        intent="model_switch_intent",
        keywords=["switch model", "change model", "use groq", "use openai", "use anthropic", "change scenario"],
        patterns=[
            r"(switch|change)\s+(to\s+)?(the\s+)?(model|llm|scenario)",
            r"\buse\s+(groq|openai|anthropic|gpt|claude|llama)\b",
        ],
        response=(
            "You can switch models or scenarios via:\n"
            "• API: POST /model/switch with {\"scenario\": 1-3, \"provider\": \"groq/openai/anthropic\"}\n"
            "• Client menu: option [2] Switch Model\n"
            "Available providers: Groq (llama3), OpenAI (gpt-4o), Anthropic (claude)"
        ),
        confidence=0.93,
        category="technical",
        priority=7,
    ),
    Rule(
        id="rule_scenarios",
        intent="scenario_info",
        keywords=["scenario", "mode", "how does it work", "which scenario", "llm mode", "rule based", "embedding"],
        patterns=[r"\b(scenario|mode)\b", r"how\s+does\s+(it|this|the\s+bot)\s+work", r"(rule.based|embedding)"],
        response=(
            "DataStream has 4 scenarios:\n"
            "1. 🤖 **LLM Only** — cloud LLM (Groq / OpenAI / Anthropic)\n"
            "2. 📝 **LLM + Rules** — rule engine first, LLM fallback\n"
            "3. 🔍 **Embedding + Rules** — semantic retrieval + rules, no LLM cost\n"
            "4. 🗄️ **Database Q&A** — Azure Synapse SQL queries + auto-charts\n\n"
            "Switch via: `POST /model/switch {\"scenario\": 1}` or client menu [2]."
        ),
        confidence=0.90,
        category="product",
        priority=6,
    ),
    Rule(
        id="rule_capabilities",
        intent="capabilities",
        keywords=[
            "what can you do", "what do you know", "list knowledge", "knowledge base",
            "what topics", "capabilities", "what can you help", "what are you", "your skills",
            "what questions", "what can i ask",
        ],
        patterns=[
            r"what\s+can\s+(you|i)\s+(do|ask|help|know)",
            r"(list|show|tell\s+me)\s+(your\s+)?(knowledge|topics|capabilities|skills)",
            r"what\s+(do\s+you|are\s+you)\s+know",
            r"what\s+(questions?\s+can|can\s+I\s+ask)",
            r"what\s+topics",
            r"what\s+do\s+you\s+know\s+about",
        ],
        response=(
            "Here’s what I can help you with:\n\n"
            "📂 **Data Pipelines (Scenario 4 — Database)**\n"
            "  • Which files are scheduled today / this week?\n"
            "  • Show last 7/14/30 days load history for [file]\n"
            "  • Which files failed yesterday?\n"
            "  • What is the status of [file_name]?\n"
            "  • Which jobs are running longer than 2 hours?\n"
            "  • Row count trend for [file] last N days\n\n"
            "🔧 **Support**\n"
            "  • Password reset steps\n"
            "  • Error troubleshooting\n"
            "  • API rate limits and quotas\n\n"
            "💰 **Pricing & Plans**\n"
            "  • Free, Standard, and Enterprise tier details\n\n"
            "🔄 **Model Control**\n"
            "  • Switch between 4 AI scenarios\n"
            "  • Change provider (Groq / OpenAI / Anthropic)\n\n"
            "*Tip: Switch to Scenario 4 for live database queries, or Scenario 1 for general AI chat.*"
        ),
        confidence=0.92,
        category="product",
        priority=8,
    ),
    Rule(
        id="rule_out_of_scope",
        intent="out_of_scope",
        keywords=[
            "weather", "temperature", "forecast", "rain", "sunny",
            "sports", "football", "cricket", "score", "match",
            "news", "politics", "stock", "bitcoin", "crypto",
            "recipe", "food", "movie", "music", "celebrity",
        ],
        patterns=[
            r"\b(weather|forecast|temperature|rain|sunny|humid)\b",
            r"\b(sports?|football|cricket|soccer|basketball|tennis|score|match)\b",
            r"\b(news|stock\s+price|crypto|bitcoin|ethereum)\b",
            r"\b(recipe|cook|movie|song|music|celebrity|actor)\b",
        ],
        response=(
            "That’s outside my area of expertise — I’m focused on **DataStream data operations**.\n\n"
            "For general questions like weather, news, or sports, switch to **Scenario 1** (LLM mode):\n"
            "`POST /model/switch {\"scenario\": 1}` — or use option **[2]** in the terminal client.\n\n"
            "**I can help you with:** file schedules, load history, failures, pricing, or support."
        ),
        confidence=0.88,
        category="general",
        priority=4,
    ),
]
