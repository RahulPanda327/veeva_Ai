"""
Local Knowledge Base Matcher — Full Embedding Edition
──────────────────────────────────────────────────────
Embeds EVERYTHING locally using sentence-transformers. No Pinecone needed.

What gets embedded:
  1. Greetings  — all trigger phrases from kb_greetings.json
                  e.g. "hi", "hello", "good morning", "heyy", "gm" ...
  2. Questions  — question text + title + description from kb_chatbot_questions_updated.json
                  e.g. "Which files failed today?" + "Failed Files" + "Shows up to 100..."

Flow on every user message:
  Step 1 — encode user message
  Step 2 — compare with ALL greeting embeddings
           if best greeting score >= 0.75 → return greeting response
  Step 3 — compare with ALL question embeddings
           if best question score >= 0.55 → fetch SQL and return
  Step 4 — low confidence → return fallback message

Place the 3 JSON files in kb/ folder at project root:
  Datastream-Chatbot/
  └── kb/
      ├── kb_greetings.json
      ├── kb_chatbot_questions_updated.json
      └── kb_sql_queries_updated.json
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

import torch
from sentence_transformers import SentenceTransformer, util

from utils.logging_util import setup_logging

logger = setup_logging("local_kb_matcher")

# ── Config ─────────────────────────────────────────────────────────────────────
KB_DIR         = Path(__file__).resolve().parent.parent / "kb"
GREETINGS_FILE = KB_DIR / "kb_greetings.json"
QUESTIONS_FILE = KB_DIR / "kb_chatbot_questions_updated.json"
SQL_FILE       = KB_DIR / "kb_sql_queries_updated.json"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # local, no API key, ~90MB

GREETING_THRESHOLD = 0.75   # above this → treat as greeting
QUESTION_THRESHOLD = 0.55   # above this → treat as SQL question


class LocalKBMatcher:

    def __init__(self):
        logger.info({"event": "local_kb_init", "kb_dir": str(KB_DIR)})

        self.greetings: list[dict] = self._load(GREETINGS_FILE)
        self.questions: list[dict] = self._load(QUESTIONS_FILE)
        self.sql_map:   dict       = self._load_sql(SQL_FILE)

        self._low_conf_greet = self._find_greet("low_confidence_fallback")
        self._out_of_scope   = self._find_greet("out_of_scope")

        logger.info({"event": "loading_embedding_model", "model": EMBEDDING_MODEL})
        self._model = SentenceTransformer(EMBEDDING_MODEL)

        # ── Greeting embeddings ─────────────────────────────────────────────────
        # Each trigger phrase is embedded individually and paired with its greet object.
        self._greeting_texts:   list[str]  = []
        self._greeting_objects: list[dict] = []

        for greet in self.greetings:
            for trigger in greet.get("triggers", []):
                self._greeting_texts.append(trigger.lower().strip())
                self._greeting_objects.append(greet)

        self._greeting_embeddings = self._model.encode(
            self._greeting_texts,
            convert_to_tensor=True,
            show_progress_bar=False,
        )
        logger.info({
            "event": "greeting_embeddings_ready",
            "total_triggers_embedded": len(self._greeting_texts),
        })

        # ── Question embeddings ─────────────────────────────────────────────────
        # Each question gets 3 entries: question text + title + description.
        # This lets "failed files today", "today failures", "what failed" all match
        # because they each hit either the question, title, or description embedding.
        self._question_texts:   list[str]  = []
        self._question_objects: list[dict] = []

        for q in self.questions:
            self._question_texts.append(q["questions"])
            self._question_objects.append(q)

            if q.get("title"):
                self._question_texts.append(q["title"])
                self._question_objects.append(q)

            if q.get("description"):
                self._question_texts.append(q["description"])
                self._question_objects.append(q)

        self._question_embeddings = self._model.encode(
            self._question_texts,
            convert_to_tensor=True,
            show_progress_bar=False,
        )
        logger.info({
            "event": "question_embeddings_ready",
            "total_texts_embedded": len(self._question_texts),
            "total_questions": len(self.questions),
        })

        logger.info({
            "event": "local_kb_ready",
            "greeting_triggers": len(self._greeting_texts),
            "question_embeddings": len(self._question_texts),
            "sql_queries": len(self.sql_map),
        })

    # ── Public: top-k search (no threshold applied) ──────────────────────────────

    def search_topk(self, query: str, k: int = 5) -> list["KBResult"]:
        """
        Return top-k question matches by cosine similarity, deduplicated by
        Query_variable. No confidence threshold applied — callers decide.
        Fetches k*3 raw indices to absorb the 3-embeddings-per-question overlap.
        """
        user_vec = self._model.encode(
            query, convert_to_tensor=True, show_progress_bar=False
        )
        scores    = util.cos_sim(user_vec, self._question_embeddings)[0]
        n_fetch   = min(k * 3, len(scores))
        top_indices = torch.topk(scores, n_fetch).indices.tolist()

        results: list[KBResult] = []
        seen: set[str] = set()
        for idx in top_indices:
            q_obj     = self._question_objects[idx]
            query_var = q_obj["Query_variable"]
            if query_var in seen:
                continue
            seen.add(query_var)
            results.append(KBResult(
                result_type="sql",
                query_variable=query_var,
                title=q_obj.get("title", ""),
                description=q_obj.get("description", ""),
                matched_question=q_obj.get("questions", ""),
                sql=self.sql_map.get(query_var, ""),
                confidence=float(scores[idx]),
            ))
            if len(results) >= k:
                break
        return results

    # ── Main entry point ─────────────────────────────────────────────────────────

    def match(self, user_message: str, user_name: str = "there") -> "KBResult":
        """
        Encode user message once, compare against:
          1. Greeting embeddings  → if score >= 0.75 return greeting
          2. Question embeddings  → if score >= 0.55 return SQL result
          3. Otherwise            → return fallback
        """
        user_vec = self._model.encode(
            user_message, convert_to_tensor=True, show_progress_bar=False
        )

        # ── Step 1: Greeting check ──────────────────────────────────────────────
        greet_scores     = util.cos_sim(user_vec, self._greeting_embeddings)[0]
        best_greet_idx   = int(greet_scores.argmax())
        best_greet_score = float(greet_scores[best_greet_idx])

        logger.info({
            "event": "greeting_match",
            "user_message": user_message,
            "best_trigger": self._greeting_texts[best_greet_idx],
            "score": round(best_greet_score, 4),
        })

        if best_greet_score >= GREETING_THRESHOLD:
            greet_obj = self._greeting_objects[best_greet_idx]
            return KBResult(
                result_type="greeting",
                response=self._format_greeting(greet_obj, user_name),
                example_prompts=greet_obj.get("example_prompts", []),
                show_examples=greet_obj.get("show_examples", False),
                confidence=best_greet_score,
            )

        # ── Step 2: Question / SQL check ────────────────────────────────────────
        quest_scores     = util.cos_sim(user_vec, self._question_embeddings)[0]
        best_quest_idx   = int(quest_scores.argmax())
        best_quest_score = float(quest_scores[best_quest_idx])

        matched_question = self._question_objects[best_quest_idx]
        matched_text     = self._question_texts[best_quest_idx]

        logger.info({
            "event": "question_match",
            "user_message": user_message,
            "best_text": matched_text,
            "query_var": matched_question.get("Query_variable"),
            "score": round(best_quest_score, 4),
        })

        if best_quest_score >= QUESTION_THRESHOLD:
            query_var = matched_question["Query_variable"]
            return KBResult(
                result_type="sql",
                query_variable=query_var,
                title=matched_question.get("title", ""),
                description=matched_question.get("description", ""),
                matched_question=matched_question.get("questions", ""),
                sql=self.sql_map.get(query_var, ""),
                confidence=best_quest_score,
            )

        # ── Step 3: Low-confidence fallback ─────────────────────────────────────
        fallback = self._low_conf_greet or self._out_of_scope
        if fallback:
            return KBResult(
                result_type="fallback",
                response=self._format_greeting(fallback, user_name),
                example_prompts=fallback.get("example_prompts", []),
                show_examples=True,
                confidence=best_quest_score,
            )

        return KBResult(
            result_type="fallback",
            response=(
                f"Sorry {user_name}, I couldn't understand that. "
                "Try: 'Which files failed today?' or 'Show today\\'s schedule'."
            ),
            confidence=best_quest_score,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────────

    def _load(self, path: Path) -> list[dict]:
        if not path.exists():
            logger.error({"event": "kb_file_missing", "path": str(path)})
            return []
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
        # raw_decode stops at the first valid JSON object, ignoring any trailing
        # content (e.g. a second JSON document appended to the file)
        try:
            data, _ = json.JSONDecoder().raw_decode(text)
        except json.JSONDecodeError as exc:
            logger.error({"event": "kb_file_parse_error", "path": str(path), "error": str(exc)})
            return []
        # Unwrap envelope objects like {"query details": [...]}
        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    return val
            return []
        return data if isinstance(data, list) else []

    def _load_sql(self, path: Path) -> dict:
        raw    = self._load(path)
        result = {}
        for item in raw:
            result.update(item)
        return result

    def _find_greet(self, category: str) -> Optional[dict]:
        for g in self.greetings:
            if g.get("category") == category:
                return g
        return None

    def _format_greeting(self, greet: dict, user_name: str) -> str:
        responses = greet.get("responses", ["Hello {user_name}!"])
        text      = random.choice(responses)
        return text.replace("{user_name}", user_name)


# ── Result class ──────────────────────────────────────────────────────────────────

class KBResult:
    def __init__(
        self,
        result_type: str,
        response: str = "",
        query_variable: str = "",
        title: str = "",
        description: str = "",
        matched_question: str = "",
        sql: str = "",
        confidence: float = 0.0,
        example_prompts: list = None,
        show_examples: bool = False,
    ):
        self.result_type      = result_type
        self.response         = response
        self.query_variable   = query_variable
        self.title            = title
        self.description      = description
        self.matched_question = matched_question
        self.sql              = sql
        self.confidence       = confidence
        self.example_prompts  = example_prompts or []
        self.show_examples    = show_examples

    def is_greeting(self) -> bool:
        return self.result_type in ("greeting", "fallback")

    def is_sql(self) -> bool:
        return self.result_type == "sql"

    def __repr__(self):
        return (
            f"KBResult(type={self.result_type}, "
            f"query_var={self.query_variable}, "
            f"confidence={self.confidence:.3f})"
        )


# ── Process-level singleton ───────────────────────────────────────────────────────

_instance: Optional[LocalKBMatcher] = None


def get_local_kb() -> LocalKBMatcher:
    global _instance
    if _instance is None:
        _instance = LocalKBMatcher()
    return _instance
