from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from config.settings import get_config
from services.base_service import ServiceFactory
from utils.logging_util import setup_logging

logger = setup_logging("model_switch")
router = APIRouter(prefix="/model", tags=["Model Management"])

SCENARIO_INFO: dict[int, str] = {
    1: "LLM Only — cloud API (Groq / OpenAI / Anthropic)",
    2: "LLM + Rule-Based — rules first, LLM fallback",
    3: "Embedding + Rule-Based — local, no LLM cost",
    4: "Database Q&A — Azure Synapse / SQL Server (template + optional LLM SQL)",
}

PROVIDER_MODELS: dict[str, list[str]] = {
    "groq": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "gemma2-9b-it", "llama-3.2-1b-preview"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    "anthropic": ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
}


class ModelStatusResponse(BaseModel):
    active_scenario: int
    scenario_description: str
    active_provider: str
    active_model: str
    temperature: float
    max_tokens: int
    memory_window_size: int
    cache_enabled: bool
    cosine_similarity_threshold: float
    available_scenarios: dict[int, str]
    available_providers: dict[str, list[str]]


class SwitchRequest(BaseModel):
    scenario: Optional[Literal[1, 2, 3, 4]] = Field(
        None, description="1=LLM, 2=LLM+Rules, 3=Embedding+Rules, 4=Database Q&A"
    )
    provider: Optional[Literal["groq", "openai", "anthropic"]] = None
    model: Optional[str] = Field(None, description="Model name for the chosen provider")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=128000)
    memory_window_size: Optional[int] = Field(None, ge=10, le=20)
    cosine_similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    rule_confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)


class SwitchResponse(BaseModel):
    message: str
    changed_fields: list[str]
    previous: dict
    current: dict


@router.get("/status", response_model=ModelStatusResponse, summary="Current runtime configuration")
def get_status(user=Depends(get_current_user)):
    cfg = get_config()
    return ModelStatusResponse(
        active_scenario=cfg.active_scenario,
        scenario_description=SCENARIO_INFO.get(cfg.active_scenario, "Unknown"),
        active_provider=cfg.active_api_provider,
        active_model=cfg.llm_model_name,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        memory_window_size=cfg.memory_window_size,
        cache_enabled=cfg.cache_enabled,
        cosine_similarity_threshold=cfg.cosine_similarity_threshold,
        available_scenarios=SCENARIO_INFO,
        available_providers=PROVIDER_MODELS,
    )


@router.post("/switch", response_model=SwitchResponse, summary="Switch scenario, provider, or model at runtime")
def switch_model(body: SwitchRequest, user=Depends(get_current_user)):
    cfg = get_config()

    previous = {
        "scenario": cfg.active_scenario,
        "provider": cfg.active_api_provider,
        "model": cfg.llm_model_name,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "memory_window_size": cfg.memory_window_size,
        "cosine_similarity_threshold": cfg.cosine_similarity_threshold,
        "rule_confidence_threshold": cfg.rule_confidence_threshold,
    }

    if body.scenario is not None:
        cfg.active_scenario = body.scenario

    if body.provider is not None:
        if body.provider not in PROVIDER_MODELS:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider!r}")
        cfg.active_api_provider = body.provider
        # Reset to provider default when switching providers without specifying a model
        if body.model is None:
            cfg.llm_model_name = PROVIDER_MODELS[body.provider][0]
        if ServiceFactory._llm is not None:
            ServiceFactory._llm.provider = body.provider

    if body.model is not None:
        cfg.llm_model_name = body.model
        if ServiceFactory._llm is not None:
            ServiceFactory._llm.cfg.llm_model_name = body.model

    if body.temperature is not None:
        cfg.temperature = body.temperature
    if body.max_tokens is not None:
        cfg.max_tokens = body.max_tokens
    if body.memory_window_size is not None:
        cfg.memory_window_size = body.memory_window_size
    if body.cosine_similarity_threshold is not None:
        cfg.cosine_similarity_threshold = body.cosine_similarity_threshold
    if body.rule_confidence_threshold is not None:
        cfg.rule_confidence_threshold = body.rule_confidence_threshold

    current = {
        "scenario": cfg.active_scenario,
        "provider": cfg.active_api_provider,
        "model": cfg.llm_model_name,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "memory_window_size": cfg.memory_window_size,
        "cosine_similarity_threshold": cfg.cosine_similarity_threshold,
        "rule_confidence_threshold": cfg.rule_confidence_threshold,
    }

    changed = [k for k in previous if previous[k] != current[k]]

    logger.info({
        "event": "model_switched",
        "user": user.username,
        "changed": changed,
        "current": current,
    })

    return SwitchResponse(
        message=f"Updated: {', '.join(changed)}" if changed else "No changes applied",
        changed_fields=changed,
        previous=previous,
        current=current,
    )
