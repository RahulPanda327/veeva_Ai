"""One-line descriptions of the ACTIVE models, for logging at each stage.

WHY THIS EXISTS
    Which LLM and which embedding model run is decided by *_ENABLED flags in
    .env, and nothing in the output said which ones won. That has already cost
    real time twice: a wrong OpenVINO base URL showed up only as hundreds of
    identical per-item warnings, and a switch of LLM provider silently changed
    which model wrote every cached insight. A model name printed where the work
    starts turns both into a single glance.

    Every stage logs through here rather than formatting its own line, so the
    same wording appears at startup, before a warm-up, before an embedding run
    and on a chat call - and adding a provider updates all of them at once.

    Resolution is deliberately lazy and never raises: a banner must not be the
    reason a warm-up fails to start, and asking for the embedder loads
    sentence-transformers (and torch) in the local case.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_ASSISTANT_DIR = str(Path(__file__).resolve().parents[2] / "ai_assistant")


def llm_line() -> str:
    """e.g. "OPENVINO / phi4-mini @ http://host:11437/v3"."""
    provider = settings.LLM_PROVIDER
    endpoint = {
        "ollama":   settings.OLLAMA_BASE_URL,
        "openai":   settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
        "groq":     "https://api.groq.com/openai/v1",
        "openvino": settings.OPENVINO_BASE_URL,
    }.get(provider, "")
    line = f"{provider.upper()} / {settings.LLM_MODEL}"
    if endpoint:
        line += f" @ {endpoint}"
    if settings.LLM_STUB_MODE:
        line += "  [STUB MODE - no real calls]"
    return line


def embedding_line() -> str:
    """e.g. "OPENVINO / bge-embed (768-dim)".

    Imports from the ai_assistant package, which is not on sys.path in every
    process that might want to log this, so the path is added here rather than
    assumed.
    """
    try:
        if _ASSISTANT_DIR not in sys.path:
            sys.path.insert(0, _ASSISTANT_DIR)
        from db_qa.embedder import get_embedder      # noqa: PLC0415

        e = get_embedder()
        return f"{e.backend.upper()} / {e.model} ({e.dim}-dim)"
    except Exception as exc:  # noqa: BLE001
        return f"unavailable ({exc})"


def store_line() -> str:
    """Where the vectors live, including the per-model collection name."""
    try:
        if _ASSISTANT_DIR not in sys.path:
            sys.path.insert(0, _ASSISTANT_DIR)
        from db_qa.vector_store import store_label   # noqa: PLC0415

        return store_label()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable ({exc})"


def log_stage(stage: str, *, embedding: bool = False, store: bool = False,
              log: logging.Logger | None = None) -> None:
    """Log the active models as a stage begins.

    `stage` names what is starting ("Warm-up", "Embedding", "Chat"), so the line
    reads as an event rather than as configuration dumped at random.
    """
    out = log or logger
    out.info("[%s] LLM: %s", stage, llm_line())
    if embedding:
        out.info("[%s] Embedding: %s", stage, embedding_line())
    if store:
        out.info("[%s] Vector store: %s", stage, store_line())
