"""
Embedding model — Pinecone vector store + local SentenceTransformer encoder.

Architecture
────────────
  query text ─► SentenceTransformer (local) ─► dense vector
                                                    │
                                                    ▼
                                            Pinecone index ◄── upsert(documents)
                                            (cosine, top-k,
                                             metadata filter)
                                                    │
                                                    ▼
                                          RetrievalResult[]

Pinecone is the persistent store — vectors and metadata survive restarts and
scale beyond memory. Only dense vectors leave the server; raw document text
is stored in the vector's metadata under the "content" key so retrieval is
self-contained (no second DB lookup needed).

Metadata filtering
──────────────────
Pass a `filter` dict to retrieve() to restrict by metadata, e.g.
  retrieve("password", filter={"category": {"$eq": "support"}})
See https://docs.pinecone.io/guides/data/filter-with-metadata for operators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from config.settings import get_config
from utils.logging_util import setup_logging

logger = setup_logging("embedding_model")


@dataclass
class Document:
    id: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    document: Document
    similarity: float
    rank: int


class EmbeddingModel:
    """Local encoder + Pinecone index. All clients are loaded lazily."""

    def __init__(self):
        self.cfg = get_config()
        self._encoder: Optional[SentenceTransformer] = None
        self._pc = None
        self._index = None

    # ── Lazy loaders ────────────────────────────────────────────────────────────

    @property
    def encoder(self) -> SentenceTransformer:
        if self._encoder is None:
            logger.info({"event": "loading_encoder", "model": self.cfg.embedding_model_name})
            self._encoder = SentenceTransformer(self.cfg.embedding_model_name)
        return self._encoder

    @property
    def index(self):
        if self._index is None:
            self._init_pinecone()
        return self._index

    def _init_pinecone(self):
        if not self.cfg.pinecone_api_key:
            raise RuntimeError(
                "PINECONE_API_KEY is not set — Scenario 3 retrieval is disabled. "
                "Add the key to .env or switch to scenario 1 or 2."
            )

        from pinecone import Pinecone, ServerlessSpec

        self._pc = Pinecone(api_key=self.cfg.pinecone_api_key)
        existing = {i["name"] for i in self._pc.list_indexes()}

        if self.cfg.pinecone_index_name not in existing:
            logger.info({
                "event": "creating_pinecone_index",
                "name": self.cfg.pinecone_index_name,
                "dimension": self.cfg.embedding_dimension,
            })
            self._pc.create_index(
                name=self.cfg.pinecone_index_name,
                dimension=self.cfg.embedding_dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=self.cfg.pinecone_cloud,
                    region=self.cfg.pinecone_region,
                ),
            )

        self._index = self._pc.Index(self.cfg.pinecone_index_name)
        logger.info({"event": "pinecone_ready", "index": self.cfg.pinecone_index_name})

    # ── Encoding ────────────────────────────────────────────────────────────────

    def encode(self, texts: list[str] | str) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]
        return self.encoder.encode(texts, normalize_embeddings=True)

    # ── Upsert / delete ─────────────────────────────────────────────────────────

    def upsert_documents(self, documents: list[dict]) -> int:
        """
        Each document: {"id"?: str, "content": str, "metadata"?: dict}.
        The raw text is stored in metadata["content"] so retrieval returns it.
        """
        if not documents:
            return 0
        contents = [d["content"] for d in documents]
        embeddings = self.encode(contents)
        vectors = []
        for i, doc in enumerate(documents):
            metadata = dict(doc.get("metadata", {}))
            metadata["content"] = doc["content"]
            vectors.append({
                "id": doc.get("id") or f"doc_{i}",
                "values": embeddings[i].tolist(),
                "metadata": metadata,
            })
        self.index.upsert(vectors=vectors)
        logger.info({"event": "documents_upserted", "count": len(vectors)})
        return len(vectors)

    def delete(self, ids: list[str]) -> int:
        if not ids:
            return 0
        self.index.delete(ids=ids)
        logger.info({"event": "documents_deleted", "count": len(ids)})
        return len(ids)

    def delete_all(self) -> bool:
        try:
            self.index.delete(delete_all=True)
            logger.info({"event": "documents_delete_all"})
            return True
        except Exception as exc:
            logger.error({"event": "delete_all_failed", "error": str(exc)})
            return False

    # ── Retrieval ───────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter: Optional[dict] = None,
    ) -> list[RetrievalResult]:
        top_k = top_k or self.cfg.top_k_retrieval
        q_vec = self.encode(query)[0].tolist()
        try:
            res = self.index.query(
                vector=q_vec,
                top_k=top_k,
                include_metadata=True,
                filter=filter,
            )
        except Exception as exc:
            logger.error({"event": "pinecone_query_failed", "error": str(exc)})
            return []

        results: list[RetrievalResult] = []
        matches = res.get("matches", []) if isinstance(res, dict) else getattr(res, "matches", [])
        for rank, match in enumerate(matches, start=1):
            # Match objects: support both dict-like and attribute access
            score = float(match["score"] if isinstance(match, dict) else match.score)
            if score < self.cfg.cosine_similarity_threshold:
                continue
            md = dict(match["metadata"] if isinstance(match, dict) else (match.metadata or {}))
            content = md.pop("content", "")
            mid = match["id"] if isinstance(match, dict) else match.id
            results.append(RetrievalResult(
                document=Document(id=mid, content=content, metadata=md),
                similarity=score,
                rank=rank,
            ))
        return results

    def format_context(self, results: list[RetrievalResult]) -> str:
        return "\n\n".join(
            f"[Source {r.rank} | cosine={r.similarity:.3f}]\n{r.document.content}"
            for r in results
        )

    def stats(self) -> dict:
        try:
            s = self.index.describe_index_stats()
            data = s if isinstance(s, dict) else s.to_dict()
            return {
                "index_name": self.cfg.pinecone_index_name,
                "total_vectors": data.get("total_vector_count", 0),
                "dimension": data.get("dimension", self.cfg.embedding_dimension),
                "namespaces": data.get("namespaces", {}),
            }
        except Exception as exc:
            return {"error": str(exc), "index_name": self.cfg.pinecone_index_name}


# Sample knowledge base — admins can seed via POST /documents/seed
SAMPLE_KNOWLEDGE_BASE: list[dict] = [
    {
        "id": "kb_001",
        "content": "DataStream is an AI-powered chatbot platform supporting multiple LLM providers: Groq, OpenAI, and Anthropic.",
        "metadata": {"category": "product_info"},
    },
    {
        "id": "kb_002",
        "content": "To reset your password go to Settings > Security > Change Password, or use the Forgot Password link on the login page.",
        "metadata": {"category": "support"},
    },
    {
        "id": "kb_003",
        "content": "DataStream has three scenarios: (1) LLM-only mode using a cloud API, (2) LLM with rule-based hybrid where rules are checked first, (3) embedding-based retrieval combined with rules.",
        "metadata": {"category": "features"},
    },
    {
        "id": "kb_004",
        "content": "API rate limits: Standard plan = 60 requests/minute, Enterprise plan = 300 requests/minute.",
        "metadata": {"category": "api"},
    },
    {
        "id": "kb_005",
        "content": "The conversation memory window stores between 10 and 20 recent exchanges to maintain context across a session.",
        "metadata": {"category": "features"},
    },
    {
        "id": "kb_006",
        "content": "JWT tokens are used for authentication. Tokens expire after 24 hours by default and must be renewed via POST /auth/login.",
        "metadata": {"category": "auth"},
    },
    {
        "id": "kb_007",
        "content": "Sentence transformers encode text into dense vector embeddings. Cosine similarity is computed between the query vector and stored document vectors to rank relevant results.",
        "metadata": {"category": "technical"},
    },
    {
        "id": "kb_008",
        "content": "Pricing: Free (100 msgs/day), Standard ($29/month, 5,000 msgs), Enterprise ($199/month, unlimited messages and priority support).",
        "metadata": {"category": "pricing"},
    },
    {
        "id": "kb_009",
        "content": "To switch models at runtime, send POST /model/switch with a JSON body specifying scenario (1-3), provider (groq/openai/anthropic), and optionally model name.",
        "metadata": {"category": "api"},
    },
    {
        "id": "kb_010",
        "content": "Groq supported models: llama3-8b-8192, llama3-70b-8192, mixtral-8x7b-32768, gemma2-9b-it. OpenAI: gpt-4o, gpt-4o-mini. Anthropic: claude-opus-4-7, claude-sonnet-4-6.",
        "metadata": {"category": "models"},
    },
]
