"""Which model turns text into vectors — one import site for both options.

    EMBEDDING_LOCAL_ENABLED=true      all-MiniLM-L6-v2 in this process (384-dim)
    EMBEDDING_OPENVINO_ENABLED=true   a model on the OpenVINO server (768-dim)

Same flag style as the LLM providers in .env: flip exactly one to true. If both
are set, local wins — stated here rather than left to import order.

WHY THE STORE MUST NOT SHARE ONE COLLECTION
    Vectors from different models are not comparable, and these two are not even
    the same width. Chroma rejects a 768-dim vector inserted into a collection
    built at 384, and — worse — if it did not, every similarity score would be
    meaningless. So collection_suffix() below namespaces the collection by model
    and width: switching the flag switches to a SEPARATE collection rather than
    corrupting the existing one.

    A collection you have never ingested into is empty. After switching, re-run
    the ingest (--embedding) or the assistant will answer "I don't have anything
    on that" for everything.

WHY LOCAL IS STILL THE DEFAULT
    It needs no network and no server. The OpenVINO option removes
    sentence-transformers + torch from the hot path (~490 MB of dependency) and
    is faster per call, but it makes every question and every ingested chunk a
    round trip to a host that has to be up.
"""
from __future__ import annotations

import os
from typing import List, Optional

import numpy as np

from utils.logging_util import setup_logging

logger = setup_logging("embedder")


def _env(name: str, default: str = "") -> str:
    """Environment value, treating a present-but-blank key as absent."""
    return (os.getenv(name) or "").strip() or default


def _flag(name: str) -> bool:
    return _env(name).lower() in ("1", "true", "yes", "on")


def _normalise(vec: np.ndarray) -> List[float]:
    """L2-normalise so cosine similarity is a plain dot product.

    Applied to BOTH backends so a score means the same thing whichever is
    active. bge models are trained expecting normalised vectors anyway.
    Guards the zero vector: an empty string would divide by zero.
    """
    vec = np.asarray(vec, dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    return (vec / norm).tolist() if norm > 0 else vec.tolist()


class LocalEmbedder:
    """sentence-transformers, loaded into this process."""

    backend = "local"

    def __init__(self) -> None:
        self.model = _env("EMBEDDING_LOCAL_MODEL", _env("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2"))
        self.dim = int(_env("EMBEDDING_LOCAL_DIMENSION", _env("EMBEDDING_DIMENSION", "384")))
        self._st = None

    def _load(self):
        """Import sentence-transformers on first use only.

        It pulls in torch: seconds of startup and hundreds of MB of RSS that a
        process which never embeds anything should not pay — and that a
        deployment using the OpenVINO backend should not pay at all.
        """
        if self._st is None:
            from sentence_transformers import SentenceTransformer   # noqa: PLC0415

            logger.info({"event": "embedder_loading_local", "model": self.model})
            self._st = SentenceTransformer(self.model)
            actual = self._st.get_sentence_embedding_dimension()
            if actual != self.dim:
                raise ValueError(
                    f"EMBEDDING_LOCAL_DIMENSION={self.dim} but {self.model} produces "
                    f"{actual}. Fix the setting and re-ingest — vectors of different "
                    f"widths cannot be compared."
                )
        return self._st

    def encode(self, text: str) -> List[float]:
        return _normalise(self._load().encode(text, show_progress_bar=False))


class OpenVINOEmbedder:
    """A model on the OpenVINO server, over its OpenAI-compatible /embeddings.

    Nothing OpenVINO-specific is installed: this is an HTTP POST, exactly like
    the openvino LLM provider in app/utils/llm_client.py.
    """

    backend = "openvino"

    def __init__(self) -> None:
        self.model = _env("EMBEDDING_OPENVINO_MODEL", "bge-embed")
        self.dim = int(_env("EMBEDDING_OPENVINO_DIMENSION", "768"))
        # Falls back to the LLM's base URL: the same server usually serves both,
        # and duplicating the host in two settings invites them to drift apart.
        base = _env("EMBEDDING_OPENVINO_BASE_URL", _env("OPENVINO_BASE_URL"))
        if not base:
            raise ValueError(
                "EMBEDDING_OPENVINO_ENABLED is true but no base URL is set. Set "
                "EMBEDDING_OPENVINO_BASE_URL, or OPENVINO_BASE_URL to reuse the "
                "LLM server, e.g. http://<host>:11437/v3"
            )
        base = base.rstrip("/")
        # Same missing-version-path guard as the LLM client: a URL without one
        # 400s on every single call, which during an ingest means hundreds of
        # failures rather than one clear error.
        if "/" not in base.split("://", 1)[-1]:
            logger.warning({"event": "embedder_base_url_no_version_path", "url": base})
            base += "/v3"
        self.url = f"{base}/embeddings"
        self.api_key = _env("EMBEDDING_OPENVINO_API_KEY", _env("OPENVINO_API_KEY"))
        # ~1400 chars is comfortably inside bge's 512-token window for ordinary
        # English. encode() shrinks further per request if the server still says
        # no, so this is a starting point rather than a hard guarantee.
        self.max_chars = int(_env("EMBEDDING_MAX_CHARS", "1400"))
        self._client = None
        self._checked = False

    def _http(self):
        if self._client is None:
            import httpx   # noqa: PLC0415

            self._client = httpx.Client(timeout=float(_env("EMBEDDING_TIMEOUT", "120")))
        return self._client

    def encode(self, text: str) -> List[float]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # bge models take at most 512 TOKENS. Chunks here run to 2000 characters,
        # which is usually under that but goes over on dense text - ids, numbers,
        # names tokenize far worse than prose, and the server rejects the whole
        # request rather than truncating ("Input length 514 longer than allowed
        # 512"). Trimming the text we EMBED is the right trade: the full chunk is
        # still stored and still handed to the LLM, only the vector is computed
        # from the leading portion. A chunk's opening lines carry its title and
        # scope, so they are the part most worth embedding anyway.
        budget = self.max_chars
        payload = text[:budget]

        for _ in range(4):
            resp = self._http().post(
                self.url, headers=headers, json={"model": self.model, "input": payload},
            )
            if resp.status_code == 200:
                break
            # Token limits cannot be predicted from character counts, so back off
            # and retry rather than guessing a universally safe budget upfront.
            if resp.status_code == 400 and "longer than allowed" in resp.text:
                budget = int(budget * 0.7)
                payload = text[:budget]
                logger.warning({"event": "embedder_input_truncated",
                                "model": self.model, "new_budget": budget})
                continue
            # The server reports an unknown model as a mediapipe graph error,
            # which is opaque unless you know the served ids differ from the
            # upstream names (bge-base-en-v1.5-int8-ov is served as "bge-embed").
            raise RuntimeError(
                f"Embedding request failed [{resp.status_code}] for model "
                f"'{self.model}' at {self.url}: {resp.text[:200]}. Check the id "
                f"against GET {self.url.rsplit('/', 1)[0]}/models."
            )
        else:
            raise RuntimeError(
                f"Embedding still rejected as too long after 4 attempts "
                f"(final budget {budget} chars) for model '{self.model}'. Lower "
                f"EMBEDDING_MAX_CHARS."
            )
        vec = resp.json()["data"][0]["embedding"]

        if not self._checked:
            self._checked = True
            if len(vec) != self.dim:
                raise ValueError(
                    f"EMBEDDING_OPENVINO_DIMENSION={self.dim} but '{self.model}' "
                    f"returns {len(vec)}. Fix the setting and re-ingest."
                )
            logger.info({"event": "embedder_openvino_ready",
                         "model": self.model, "dim": self.dim, "url": self.url})
        return _normalise(vec)


_instance = None


def get_embedder():
    """The configured embedder (a process-level singleton)."""
    global _instance
    if _instance is None:
        if _flag("EMBEDDING_LOCAL_ENABLED"):
            _instance = LocalEmbedder()
        elif _flag("EMBEDDING_OPENVINO_ENABLED"):
            _instance = OpenVINOEmbedder()
        else:
            # Neither flag set: keep working rather than refusing to start, and
            # say so, since an unset flag is far more likely a forgotten edit
            # than a deliberate choice.
            logger.warning({"event": "embedder_no_flag_set", "using": "local"})
            _instance = LocalEmbedder()
    return _instance


def collection_suffix() -> str:
    """Namespace fragment identifying the active embedding model.

    Appended to the Chroma collection name so the 384-dim and 768-dim stores are
    physically separate: switching the flag can then never insert a vector of one
    width into a collection built for another.
    """
    e = get_embedder()
    slug = "".join(c if c.isalnum() else "_" for c in e.model.lower()).strip("_")
    return f"{slug}_{e.dim}"
