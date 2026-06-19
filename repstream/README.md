# RepStream — AI-Powered CRM Intelligence Platform

RepStream gives pharmaceutical sales reps GPT-4o-powered intelligence across three modules: **Territory Prioritization**, **New Writer Identification**, and **Objection Handler**. Data is read-only from the `hub_insight360` schema in PostgreSQL; all heavy computation runs as weekly Celery batches so API endpoints respond from pre-computed Redis cache.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser  →  React + TanStack Query + Tailwind CSS  (port 80/5173)  │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ HTTP /api/v1/...
┌──────────────────────────▼───────────────────────────────────────────┐
│  FastAPI Backend  (port 8000)                                         │
│  ├── routers/  territory_prioritization, new_writer_id, objection    │
│  ├── services/ feature engineering, LLM insights, ML scoring         │
│  └── utils/    llm_client (GPT-4o + cache), auth (JWT), cache (Redis)│
└────────┬────────────────────────┬────────────────────────────────────┘
         │ SQLAlchemy (read-only)  │ Redis GET
┌────────▼──────────┐    ┌────────▼──────────┐
│  PostgreSQL        │    │  Redis 7           │
│  hub_insight360    │    │  • LLM cache (24h) │
│  (views + cooked)  │    │  • List cache (1h) │
└───────────────────┘    │  • Celery broker   │
                         └───────────────────┘
         ▲
┌────────┴──────────────────────┐
│  Celery Worker + Beat          │
│  Weekly Monday 02:00 UTC batch │
│  → refresh territory / writers │
│  → refresh objections cache    │
└───────────────────────────────┘
```

### Key design decisions

| Decision | Rationale |
|---|---|
| Read-only SQLAlchemy models | Protects warehouse data; no accidental writes |
| Redis cache + Celery batch | API never runs heavy joins on request; pre-warmed every Monday |
| GPT-4o via `llm_client` | Centralized retry / rate-limit / 24h caching; swap model in `.env` |
| JWT bearer token | Stateless auth; `territory_id` extracted from token to scope all queries |

---

## Local Setup

### Prerequisites
- Docker & Docker Compose v2
- Node.js 20 + npm (for frontend dev only)
- Python 3.12 + pip (for backend dev only)

### 1 — Clone and configure

```bash
git clone <repo-url> repstream
cd repstream

# Copy and fill in the backend environment file
cp backend/.env.example backend/.env
# Edit: DATABASE_URL, OPENAI_API_KEY, JWT_SECRET (minimum required)
```

### 2 — Start all services with Docker Compose

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/api/docs |
| ReDoc | http://localhost:8000/api/redoc |

### 3 — Frontend dev server (hot reload)

```bash
cd frontend
npm install
npm run dev       # → http://localhost:5173
```

### 4 — Backend dev server

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env                                 # fill in values
uvicorn app.main:app --reload
```

### 5 — Run tests

```bash
cd backend
pytest tests/ -v
```

### 6 — Trigger a manual Celery batch refresh

```bash
# With Docker Compose running:
docker compose exec worker celery -A app.tasks.celery_app call app.tasks.refresh_territory.refresh_all_territories
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL connection string (psycopg2 format) |
| `HUB_SCHEMA` | `hub_insight360` | Schema for warehouse views |
| `DS_SCHEMA` | `ds_hub_syndb` | Schema for enriched/cooked tables |
| `OPENAI_API_KEY` | — | **Required.** GPT-4o API key |
| `OPENAI_MODEL` | `gpt-4o` | Model name (override for testing) |
| `OPENAI_MAX_RETRIES` | `3` | LLM retry attempts on rate limit |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for cache + call-prep sets |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery task broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Celery result store |
| `JWT_SECRET` | — | **Required.** HS256 signing secret |
| `JWT_EXPIRE_MINUTES` | `480` | Token lifetime (8 hours) |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins (JSON array) |
| `RX_TREND_HIGH_THRESHOLD` | `15.0` | % above which HCP is HIGH priority |
| `RX_TREND_LOW_THRESHOLD` | `-10.0` | % below which HCP is LOW priority |
| `WEEKLY_TARGET_RATIO` | `0.65` | `ceil(HIGH_count * ratio)` = weekly visits |
| `OBJECTION_HIGH_THRESHOLD` | `8` | Call count above which objection is HIGH |
| `OBJECTION_MEDIUM_MIN` | `3` | Minimum call count for MEDIUM label |

---

## API Endpoint Reference

All endpoints require `Authorization: Bearer <token>` header.  
Token must contain `sub` (rep_id) and `territory_id` claims.

### Module 1 — Territory Prioritization

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/territory/summary` | KPI tiles: total HCPs, High/Med/Low counts, weekly target |
| `GET` | `/api/v1/territory/hcp-list` | Ranked HCP list with AI insights, Rx Q1/Q4, priority tier |
| `GET` | `/api/v1/territory/hcp/{hcp_id}/insight` | On-demand: regenerate AI insight for one HCP |

**Sample response — `GET /api/v1/territory/summary`**
```json
{
  "total_hcps": 142,
  "high_priority_count": 38,
  "medium_priority_count": 67,
  "low_priority_count": 37,
  "weekly_target": 25,
  "period": "Q1 2025",
  "territory_id": "TERR-001",
  "territory_name": "Boston North"
}
```

### Module 2 — New Writer Identification

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/new-writers/candidates` | Non-writers with peer match %, ICD-10 codes, Rx breakdown |
| `POST` | `/api/v1/new-writers/{hcp_id}/approach-brief` | Generate GPT-4o warm outreach brief |

**Sample response — `GET /api/v1/new-writers/candidates[0]`**
```json
{
  "hcp_id": "HCP002",
  "name": "Dr. John Doe",
  "specialty": "Internal Medicine",
  "in_class_rx_q1": 12,
  "brand_rx_q1": 0,
  "brand_rx_q4": 0,
  "competitor_brand": "Creon",
  "competitor_volume": 12,
  "peer_match_pct": 78,
  "peer_name": "Dr. Alice Johnson",
  "matched_icd10_codes": ["K86.1", "K86.81"]
}
```

### Module 3 — Objection Handler

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/objections/list` | Ranked objections with frequency label and success rate |
| `GET` | `/api/v1/objections/{objection_id}/response` | MLR-approved response + SKU + success rate |
| `POST` | `/api/v1/objections/{objection_id}/add-to-call-prep` | Flag objection for next call prep |

---

## Business Logic Rules

### Priority Tiers (Module 1)
```
HIGH   : rx_trend > 15%  OR  rx_q1 > 75th percentile of territory
LOW    : rx_trend < -10%
MEDIUM : everything else
Weekly target = ceil(HIGH_count × 0.65)
```

### Non-Writer Detection (Module 2)
```
Candidate = in_class_rx_q1 > 0 AND brand_rx_q1 = 0 AND brand_rx_q4 = 0
```

### Objection Frequency (Module 3)
```
HIGH   : call_count > 8
MEDIUM : 3 ≤ call_count ≤ 8
LOW    : call_count < 3
Success rate = calls with Rx within 30 days / total calls with objection
```

---

## Project Structure

```
repstream/
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI entry point
│   │   ├── config.py             Pydantic settings
│   │   ├── database.py           SQLAlchemy engine + session
│   │   ├── models/               Read-only ORM models (hub_insight360)
│   │   ├── schemas/              Pydantic request/response models
│   │   ├── routers/              FastAPI route handlers (3 modules)
│   │   ├── services/             Business logic per module
│   │   ├── tasks/                Celery batch refresh tasks
│   │   └── utils/                LLM client, Redis cache, JWT auth
│   └── tests/                    pytest unit tests (mocked DB)
└── frontend/
    └── src/
        ├── api/                  Axios API clients
        ├── components/           React UI components
        ├── hooks/                TanStack Query data hooks
        ├── pages/                Page-level route components
        └── types/                TypeScript interfaces
```
