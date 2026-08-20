# from contextlib import asynccontextmanager

# from fastapi import FastAPI, Request
# from fastapi.middleware.cors import CORSMiddleware
# ### below is the comment out for now, but can be re-enabled when we add the web UI back in

# # from fastapi.responses import JSONResponse, RedirectResponse
# # from fastapi.staticfiles import StaticFiles

# from api.routes import auth, chat, documents, model_switch, sessions
# from api.routes.database import router as db_router, charts_router
# from config.settings import get_config
# from middlewares.request_logging import RequestLoggingMiddleware
# from services.base_service import ServiceFactory
# from utils.logging_util import setup_logging

# logger = setup_logging("main")


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     cfg = get_config()
#     logger.info({
#         "event": "startup",
#         "scenario": cfg.active_scenario,
#         "provider": cfg.active_api_provider,
#         "model": cfg.llm_model_name,
#     })

#     ServiceFactory.initialize()

#     # Pre-warm the local encoder (Pinecone connects lazily on first query)
#     if cfg.pinecone_api_key:
#         try:
#             ServiceFactory.get_embeddings().encoder  # loads SentenceTransformer
#             logger.info({"event": "encoder_ready", "model": cfg.embedding_model_name})
#         except Exception as exc:
#             logger.error({"event": "encoder_warmup_failed", "error": str(exc)})
#     else:
#         logger.warning({"event": "pinecone_not_configured", "note": "Scenario 3 unavailable until PINECONE_API_KEY is set"})

#     yield

#     logger.info({"event": "shutdown"})


# app = FastAPI(
#     title="DataStream Chatbot API",
#     description=(
#         "Multi-scenario AI chatbot.\n\n"
#         "**Scenarios**\n"
#         "- `1` LLM Only (Groq / OpenAI / Anthropic)\n"
#         "- `2` LLM + Rule-Based (rules first, LLM fallback)\n"
#         "- `3` Embedding + Rule-Based (local, no LLM cost)\n"
#         "- `4` Database Q\u0026A (Azure Synapse — template SQL + optional LLM SQL + charts)\n\n"
#         "Switch at runtime via `POST /model/switch`."
#     ),
#     version="1.0.0",
#     lifespan=lifespan,
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
# app.add_middleware(RequestLoggingMiddleware)


# @app.exception_handler(Exception)
# async def unhandled_exception_handler(request: Request, exc: Exception):
#     request_id = getattr(request.state, "request_id", "-")
#     logger.error({
#         "event": "unhandled_exception",
#         "request_id": request_id,
#         "path": request.url.path,
#         "error": str(exc),
#         "type": type(exc).__name__,
#     })
#     return JSONResponse(
#         status_code=500,
#         content={"detail": "Internal server error", "request_id": request_id},
#     )

# app.include_router(auth.router)
# app.include_router(chat.router)
# app.include_router(sessions.router)
# app.include_router(documents.router)
# app.include_router(model_switch.router)
# app.include_router(db_router)
# app.include_router(charts_router)

# #below is the comment out for now, but can be re-enabled when we add the web UI back in

# # # ── Serve Web UI ──────────────────────────────────────────────────────────────
# # app.mount("/ui", StaticFiles(directory="templates", html=True), name="ui")


# # @app.get("/", include_in_schema=False)
# # def root_redirect():
# #     """Redirect root to the Web UI."""
# #     return RedirectResponse(url="/ui/index.html")


# @app.get("/health", tags=["Health"])
# def health():
#     cfg = get_config()
#     return {
#         "status": "healthy",
#         "active_scenario": cfg.active_scenario,
#         "provider": cfg.active_api_provider,
#         "model": cfg.llm_model_name,
#     }


# if __name__ == "__main__":
#     import uvicorn
#     cfg = get_config()
#     uvicorn.run("main:app", host=cfg.app_host, port=cfg.app_port, reload=True)


from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── below is commented out — built-in HTML frontend not used with React UI ───
# from fastapi.responses import JSONResponse, RedirectResponse
# from fastapi.staticfiles import StaticFiles

from api.routes import auth, chat, documents, model_switch, sessions
from api.routes.database import router as db_router, charts_router
from api.routes.export import router as export_router
from api.routes.feedback import router as feedback_router
from api.routes.application_logs_route import router as app_logs_router
from config.settings import get_config
from middlewares.request_logging import RequestLoggingMiddleware
from services.base_service import ServiceFactory
from utils.logging_util import setup_logging

logger = setup_logging("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    logger.info({
        "event": "startup",
        "scenario": cfg.active_scenario,
        "provider": cfg.active_api_provider,
        "model": cfg.llm_model_name,
    })

    ServiceFactory.initialize()

    # # Pre-warm the local encoder (Pinecone connects lazily on first query)
    # if cfg.pinecone_api_key:
    #     try:
    #         ServiceFactory.get_embeddings().encoder  # loads SentenceTransformer
    #         logger.info({"event": "encoder_ready", "model": cfg.embedding_model_name})
    #     except Exception as exc:
    #         logger.error({"event": "encoder_warmup_failed", "error": str(exc)})
    # else:
    #     logger.warning({"event": "pinecone_not_configured", "note": "Scenario 3 unavailable until PINECONE_API_KEY is set"})

    yield

    logger.info({"event": "shutdown"})


app = FastAPI(
    title="DataStream Chatbot API",
    description=(
        "Multi-scenario AI chatbot.\n\n"
        "**Scenarios**\n"
        "- `1` LLM Only (Groq / OpenAI / Anthropic)\n"
        "- `2` LLM + Rule-Based (rules first, LLM fallback)\n"
        "- `3` Embedding + Rule-Based (local, no LLM cost)\n"
        "- `4` Database Q&A (Azure Synapse — template SQL + optional LLM SQL + charts)\n\n"
        "Switch at runtime via `POST /model/switch`."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "-")
    logger.error({
        "event": "unhandled_exception",
        "request_id": request_id,
        "path": request.url.path,
        "error": str(exc),
        "type": type(exc).__name__,
    })
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )

# ── Existing routers (unchanged) ──────────────────────────────────────────────
app.include_router(auth.router)           # /auth/login, /auth/me
app.include_router(chat.router)           # /chat  (now also returns `reply` field)
app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(model_switch.router)
app.include_router(db_router)
app.include_router(charts_router)
app.include_router(export_router)
app.include_router(feedback_router)
app.include_router(app_logs_router)       # /logs — interaction lifecycle + auth events
# ── ADDED: React frontend router — registers POST /login ─────────────────────
# React calls POST /api/login → Vite proxy rewrites to POST /login on port 8000
app.include_router(auth.react_router)

# ── below is commented out — built-in HTML frontend not used with React UI ───
# app.mount("/ui", StaticFiles(directory="templates", html=True), name="ui")
#
# @app.get("/", include_in_schema=False)
# def root_redirect():
#     """Redirect root to the Web UI."""
#     return RedirectResponse(url="/ui/index.html")


@app.get("/health", tags=["Health"])
def health():
    cfg = get_config()
    return {
        "status": "healthy",
        "active_scenario": cfg.active_scenario,
        "provider": cfg.active_api_provider,
        "model": cfg.llm_model_name,
    }


if __name__ == "__main__":
    import uvicorn
    cfg = get_config()
    uvicorn.run("main:app", host=cfg.app_host, port=cfg.app_port, reload=True)