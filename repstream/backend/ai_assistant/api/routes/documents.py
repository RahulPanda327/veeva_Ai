"""
Document / knowledge-base management routes for the Pinecone index.

POST   /documents           upsert one or more documents
DELETE /documents/{id}      delete by ID
DELETE /documents           delete all (admin reset)
GET    /documents/stats     index statistics
POST   /documents/seed      load the bundled sample knowledge base
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from services.base_service import ServiceFactory

router = APIRouter(prefix="/documents", tags=["Knowledge Base"])


class DocumentIn(BaseModel):
    id: Optional[str] = Field(None, description="Stable ID; auto-generated if omitted")
    content: str = Field(..., min_length=1, max_length=8000)
    metadata: dict = Field(default_factory=dict, description="Arbitrary key-value tags for filtering")


class UpsertRequest(BaseModel):
    documents: list[DocumentIn] = Field(..., min_length=1, max_length=200)


class UpsertResponse(BaseModel):
    upserted: int


class StatsResponse(BaseModel):
    index_name: str
    total_vectors: int = 0
    dimension: int = 0
    namespaces: dict = {}
    error: Optional[str] = None


@router.post("", response_model=UpsertResponse, summary="Upsert documents into the Pinecone index")
def upsert(body: UpsertRequest, user=Depends(get_current_user)):
    em = ServiceFactory.get_embeddings()
    try:
        count = em.upsert_documents([
            {"id": d.id, "content": d.content, "metadata": d.metadata}
            for d in body.documents
        ])
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return UpsertResponse(upserted=count)


@router.delete("/{doc_id}", summary="Delete one document by ID")
def delete_doc(doc_id: str, user=Depends(get_current_user)):
    em = ServiceFactory.get_embeddings()
    try:
        em.delete([doc_id])
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"deleted": doc_id}


@router.delete("", summary="Delete ALL documents — irreversible")
def delete_all(user=Depends(get_current_user), confirm: bool = False):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Pass ?confirm=true to delete the entire index contents",
        )
    em = ServiceFactory.get_embeddings()
    try:
        ok = em.delete_all()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"deleted_all": ok}


@router.get("/stats", response_model=StatsResponse, summary="Pinecone index statistics")
def stats(user=Depends(get_current_user)):
    em = ServiceFactory.get_embeddings()
    try:
        return StatsResponse(**em.stats())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/seed", response_model=UpsertResponse, summary="Seed the bundled sample knowledge base")
def seed(user=Depends(get_current_user)):
    from models.embedding_model import SAMPLE_KNOWLEDGE_BASE
    em = ServiceFactory.get_embeddings()
    try:
        count = em.upsert_documents(SAMPLE_KNOWLEDGE_BASE)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return UpsertResponse(upserted=count)
