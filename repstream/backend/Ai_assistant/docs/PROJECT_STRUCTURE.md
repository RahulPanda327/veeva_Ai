# DataStream Chatbot — Project Structure

```
Datastream-Chatbot-demo_branch_v1/
│
├── main.py                          # FastAPI app entry point — registers all routers, lifespan startup
├── client.py                        # Terminal CLI client — interactive chat, session & model menus
├── requirements.txt                 # Python package dependencies (fastapi, uvicorn, groq, pyodbc, etc.)
├── .env                             # Live secrets & runtime config (git-ignored)
├── .env.example                     # Template showing every supported env variable with comments
├── .gitignore                       # Standard Python + secrets gitignore rules
├── .pre-commit-config.yaml          # Pre-commit hook config (lint, format)
├── Dockerfile                       # Container build definition for deployment
├── README.md                        # Project overview and quick-start notes
│
├── api/                             # HTTP layer — FastAPI app wiring
│   ├── __init__.py
│   ├── dependencies.py              # Shared FastAPI Depends: auth, service, session-store providers
│   └── routes/                      # One file per feature area
│       ├── __init__.py
│       ├── auth.py                  # POST /auth/login, GET /auth/me — JWT token issuance
│       ├── chat.py                  # POST /chat, POST /chat/stream, DELETE context, GET memory/stats
│       ├── database.py              # GET /db/test|templates|schema, POST /db/sql, GET /charts/{file}
│       ├── documents.py             # POST /documents, POST /documents/seed, DELETE /documents/{id}
│       ├── model_switch.py          # GET /model/status, POST /model/switch — live runtime config
│       └── sessions.py              # GET/PATCH/DELETE /sessions — conversation history management
│
├── auth/                            # Authentication internals
│   ├── __init__.py                  # Exports TokenData, verify_password
│   ├── jwt_handler.py               # JWT creation, decoding, token model (HS256)
│   └── password.py                  # bcrypt hash verify + plain-text fallback for dev
│
├── config/                          # App configuration
│   ├── __init__.py
│   └── settings.py                  # AppConfig (pydantic-settings) — 42 env-driven params, lru_cache singleton
│
├── db_qa/                           # Scenario 4 toolkit (Database Q&A)
│   ├── __init__.py                  # Re-exports SQLQueryRouter, DB_TEMPLATES, ChartGenerator, SCHEMA_CONTEXT
│   ├── chart_generator.py           # matplotlib auto-detect line/bar chart → saves PNG + returns base64
│   ├── sql_query_router.py          # Maps NL questions → SQL templates via regex/intent + SCHEMA_CONTEXT
│   └── sql_templates.py             # 17 parameterized SQL templates for Azure Synapse queries
│
├── dbs/                             # Persistent storage clients
│   ├── __init__.py
│   ├── chatbot.db                   # SQLite file — sessions + message history (auto-created)
│   ├── session_store.py             # SQLite CRUD — create/get/list/delete sessions and messages
│   └── sql_server_client.py         # pyodbc wrapper for Azure Synapse — read-only enforced, row cap
│
├── memory/                          # In-process conversation state
│   ├── __init__.py
│   └── conversation_memory.py       # LRU sliding-window history + response cache (cachetools TTL)
│
├── middlewares/                     # ASGI middleware
│   ├── __init__.py
│   └── request_logging.py           # Logs every request with method, path, status, latency, request-id
│
├── models/                          # AI model wrappers
│   ├── __init__.py
│   ├── embedding_model.py           # SentenceTransformer encoder + Pinecone vector store client
│   ├── llm_client.py                # Unified LLM caller — Groq / OpenAI / Anthropic with streaming
│   └── rule_based_model.py          # Keyword + regex rule engine (12 rules: greeting, weather, …)
│
├── services/                        # Business logic — one service per scenario
│   ├── __init__.py
│   ├── base_service.py              # Abstract BaseService + ChatRequest/Response dataclasses + ServiceFactory
│   ├── scenario_1_llm.py            # Scenario 1 — pure LLM chat (Groq/OpenAI/Anthropic), streaming
│   ├── scenario_2_llm_rules.py      # Scenario 2 — rule engine first, LLM fallback, streaming
│   ├── scenario_3_embedding_rules.py# Scenario 3 — Pinecone semantic retrieval + rules, no LLM cost
│   └── scenario_4_database.py      # Scenario 4 — SQL template/LLM → Synapse execute → format → chart
│
├── utils/                           # Shared utilities
│   └── logging_util.py              # setup_logging() — JSON structured logger factory
│
├── tests/                           # Test suite
│   ├── __init__.py
│   ├── test_api.py                  # Live integration test — hits all API endpoints against localhost:8000
│   └── test_rules.py                # Isolated unit test for the rule-engine matching logic
│
├── docs/                            # Documentation
│   ├── API_GUIDE.md                 # Postman & operations guide — all endpoints with examples
│   ├── PROJECT_STRUCTURE.md         # This file — folder layout and dependency flow
│   └── architecture.md              # High-level system design notes
│
├── charts/                          # Runtime output — auto-generated chart PNGs land here
│   └── .gitkeep
│
├── templates/                       # Reserved for future Jinja2 / prompt templates
├── helpers/                         # Reserved for future shared helper modules
├── mcp_servers/                     # Reserved for MCP (Model Context Protocol) server definitions
├── mcp_servers_helpers/             # Reserved for MCP server helper utilities
└── node_server/                     # Reserved for a companion Node.js/frontend server
```

---

## Dependency Flow

```
main.py
  └── api/routes/*          (HTTP endpoints)
        └── api/dependencies.py
              └── services/base_service.py → ServiceFactory
                    ├── services/scenario_1_llm.py       → models/llm_client.py
                    ├── services/scenario_2_llm_rules.py → models/llm_client.py + models/rule_based_model.py
                    ├── services/scenario_3_embedding_rules.py → models/embedding_model.py + models/rule_based_model.py
                    └── services/scenario_4_database.py  → dbs/sql_server_client.py
                                                            db_qa/sql_query_router.py → db_qa/sql_templates.py
                                                            db_qa/chart_generator.py
                    └── (all scenarios) → memory/conversation_memory.py → dbs/session_store.py
```

---

## What changed in this reorganization

| Before                                       | After                                  |
|----------------------------------------------|----------------------------------------|
| `test_api.py`, `test_rules.py` at root       | `tests/test_api.py`, `tests/test_rules.py` |
| `architecture.md`, `API_GUIDE.md` at root    | `docs/architecture.md`, `docs/API_GUIDE.md` |
| `PROJECT_STRUCTURE.md` at root               | `docs/PROJECT_STRUCTURE.md`            |
| `models/sql_templates.py`                    | `db_qa/sql_templates.py`               |
| `models/sql_query_router.py`                 | `db_qa/sql_query_router.py`            |
| `models/chart_generator.py`                  | `db_qa/chart_generator.py`             |
| Empty stubs at root (5 JSONs, `tools_embedding.py`, `env.dev`, `utils/client.py`) | Removed |

**Rationale**: `models/` now holds *only* AI model wrappers (LLM, embedding, rules). All
Scenario 4 (Database Q&A) machinery — SQL templates, query router, chart generator —
lives together under `db_qa/`, so future debugging starts from a single folder.

---

## Key Config Env Variables (`.env`)

| Variable | Controls |
|---|---|
| `ACTIVE_SCENARIO` | Which scenario boots: 1/2/3/4 |
| `ACTIVE_API_PROVIDER` | LLM provider: groq / openai / anthropic |
| `GROQ_API_KEY` | Groq API authentication |
| `PINECONE_API_KEY` | Enables Scenario 3 vector store |
| `DB_HOST / DB_NAME / DB_USER / DB_PASSWORD` | Azure Synapse connection (Scenario 4) |
| `CHART_OUTPUT_DIR` | Folder where chart PNGs are saved |
| `JWT_SECRET_KEY` | Signs all auth tokens |
| `RULE_CONFIDENCE_THRESHOLD` | Min score for a rule to fire (default 0.80) |
| `COSINE_SIMILARITY_THRESHOLD` | Min Pinecone similarity to use a doc (default 0.70) |
| `DB_LLM_FALLBACK_ENABLED` | Allow LLM to generate SQL when no template matches |
