# RepStream — AI-Powered Pharma CRM Intelligence Platform

RepStream gives pharmaceutical sales reps GPT-4o-powered intelligence across four modules: **Territory Prioritization**, **New Writer Identification**, **Objection Handler**, and **Action Center (Active Alerts)**. A FastAPI backend, backed live by Azure Synapse Analytics, powered by GPT-4o, IsolationForest, and Linear Regression ML models.

---

## Key Features

- **Real DB data only, no fake fallbacks** — every module reads live from Azure Synapse (`hub_insight360` schema). Fields with no real source column return `null`/`""` instead of made-up values.
- **GPT-4o insights grounded in real data** — every AI-generated field (counter-scripts, HCP insights, outreach emails, warm approaches) is prompted with that specific record's own numbers, never generic text.
- **24h (configurable) response cache** — no Redis required for this; disk-persisted, survives `--reload` restarts.
- **Real downloadable payer-access documents** — served directly from the backend as clickable links.
- **Background-warmed AI caches** — GPT-4o output for insights/approach briefs/emails is pre-generated and disk-cached so the UI never blocks on a live LLM call.

---

## Project Structure

```
repstream/
├── backend/                        ← FastAPI app — run everything from here
│   ├── main.py                     ← FastAPI entry point (NOT app/main.py)
│   ├── app/
│   │   ├── config.py               ← Environment config (reads .env)
│   │   ├── database.py             ← Azure Synapse DB connection
│   │   ├── routers/                ← API route handlers
│   │   ├── services/               ← Business logic + ML models + GPT-4o prompts
│   │   ├── schemas/                ← Pydantic response models
│   │   ├── models/                 ← SQLAlchemy DB models (real Synapse column mappings)
│   │   └── utils/
│   │       ├── response_cache.py   ← 24h (configurable) GET-response cache, no Redis
│   │       ├── auth.py             ← JWT auth + DEV_SKIP_AUTH bypass
│   │       └── cache.py            ← Redis-based cache (currently unused/no-op)
│   ├── scripts/
│   │   ├── train_ml_models.py      ← Run ONCE to generate .pkl files
│   │   ├── seed_demo_data.py       ← Seed demo data into DB
│   │   ├── generate_test_token.py  ← Generate JWT token for testing
│   │   └── clear_cache.py          ← Clear all 4 local disk caches
│   ├── models/                     ← Auto-created after training
│   │   ├── isolation_forest.pkl    ← Trained IsolationForest model
│   │   ├── scaler.pkl              ← StandardScaler
│   │   └── detected_alerts.pkl     ← Cached ML alert results (fallback only)
│   ├── resources/                  ← Real payer-access documents served as download links
│   │   ├── 1_PAP_Enrollment_Form_Template.docx
│   │   ├── 2_Prior_Authorization_Template.docx
│   │   ├── 3_Copay_Bridge_Program_Template.docx
│   │   └── 4_Formulary_Appeal_Template.docx
│   ├── kb/                         ← Knowledge base files
│   ├── .insight_cache.json         ← GPT-4o Territory insights (auto-created, git-ignored)
│   ├── .warm_approach_cache.json   ← GPT-4o New Writer warm-approach text (auto-created, git-ignored)
│   ├── .approach_email_cache.json  ← GPT-4o outreach email drafts (auto-created, git-ignored)
│   ├── .endpoint_response_cache.json ← 24h response cache data (auto-created, git-ignored)
│   ├── requirements.txt
│   └── .env                        ← You create this (see Step 2)
└── docker-compose.yml
```

> **Note:** the 4 `.json` files under `backend/` starting with a dot are AI/response caches auto-generated at runtime — they are not source code and should never be committed. `app/utils/response_cache.py` (the file that *creates* the cache) is source code and must never be deleted.

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Backend |
| ODBC Driver 17 | latest | Azure Synapse DB connection |
| Redis | 7+ | Optional — only needed for Celery/legacy cache, not for the 24h response cache |

---

## Step 1 — Go to the backend folder

> All backend commands run from inside `repstream/backend/`

```bash
cd repstream/backend
```

---

## Step 2 — Create `.env` file

Create a file named `.env` inside `repstream/backend/` (see `.env.example` for the full template):

```env
# ── Database — Azure Synapse Analytics ────────────────────────────────────
DB_HOST=ds-hub-syn-wks.sql.azuresynapse.net
DB_PORT=1433
DB_NAME=ds_hub_syndb
DB_USER=hub_ds_ai_usr
DB_PASSWORD=your_db_password_here
HUB_SCHEMA=hub_insight360
DS_SCHEMA=ds_hub_syndb

# ── OpenAI ─────────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o

# ── Response Cache (no Redis needed) ─────────────────────────────────────
# How long a GET endpoint's response is cached, in minutes. 1440 = 24 hours.
RESPONSE_CACHE_TTL_MINUTES=1440

# ── Auth ───────────────────────────────────────────────────────────────────
JWT_SECRET=your-secret-key-here

# ── Redis (optional — Celery / legacy cache only) ─────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Dev flags ──────────────────────────────────────────────────────────────
DEV_SKIP_AUTH=False   # true = skip JWT, auto-login as REP001 (local dev only)
LLM_STUB_MODE=False   # true = skip GPT-4o calls, return stub text (no API key needed)
```

---

## Step 3 — Create virtual environment and install dependencies

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate

pip install -r requirements.txt
```

---

## Step 4 — Train ML models (run ONCE only)

This generates `.pkl` files so the app loads ML results instantly on every subsequent start — no retraining, no DB query.

```bash
python scripts/train_ml_models.py
```

**What it does:**
- Connects to Azure Synapse and loads 12 months of Rx data
- Trains **IsolationForest** → detects competitive Rx anomalies
- Runs **Linear Regression** → detects gradual HCP prescribing drift
- Saves 3 files to `repstream/backend/models/`

> This is only a fallback path — Active Alerts primarily reads pre-computed alerts directly from `insight360_active_alerts` in Synapse. The ML pipeline only runs if that table is empty or unreachable.

> To retrain with fresh data, run this script again — it deletes old files and retrains automatically.

---

## Step 5 — Generate a test JWT token

```bash
python scripts/generate_test_token.py
```

Copy the token — you need it to call any API endpoint from Swagger, **unless** `DEV_SKIP_AUTH=True` in `.env`, in which case every request is automatically treated as `REP001`.

---

## Step 6 — Start the backend

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> `main.py` lives directly in `repstream/backend/`, **not** inside `app/` — the entry point is `main:app`, not `app.main:app`.

Backend is now running at:

| URL | Description |
|---|---|
| `http://localhost:8000/health` | Health check |
| `http://localhost:8000/api/docs` | Swagger UI (interactive API) |
| `http://localhost:8000/api/redoc` | ReDoc API reference |

---

## Full Startup Order (quick reference)

```
1. cd repstream/backend
2. venv\Scripts\activate                                  ← activate venv
3. python scripts/train_ml_models.py                      ← FIRST TIME ONLY
4. uvicorn main:app --reload --port 8000                  ← start backend
```

---

## API Response Format

Every endpoint returns its data directly — no wrapper object. A list endpoint returns `{"items": [...], "total": ...}` as-is; a detail endpoint returns the object as-is.

---

## Caching — 4 disk-based caches (no Redis)

RepStream has 4 separate local JSON caches, all living in `backend/` as git-ignored dotfiles, auto-created on first use:

| File | What it holds | Expires on its own? |
|---|---|---|
| `.endpoint_response_cache.json` | Full HTTP response for every GET endpoint, keyed by `method + path + query params + caller` | Yes — after `RESPONSE_CACHE_TTL_MINUTES` (`.env`, default 1440 = 24h) |
| `.insight_cache.json` | Territory Prioritization's GPT-4o HCP insights | **No** |
| `.warm_approach_cache.json` | New Writer ID's GPT-4o warm-approach text | **No** |
| `.approach_email_cache.json` | New Writer ID's GPT-4o outreach emails | **No** |

**How the response cache behaves:**
- **First hit**: runs the real query/LLM pipeline, stores the result, returns it.
- **Repeat hit within the TTL window**: returns the stored response instantly — no DB or GPT-4o call.
- **Repeat hit after the TTL expires**: the stale entry is deleted, a fresh one is computed and re-stored under the same key. This repeats indefinitely, on every request — it's not a one-time cache.

**The 3 AI-generation caches never expire on their own.** Once GPT-4o writes something for an HCP, it's kept forever — regenerating means a real (slow, costs money) LLM call, so nothing clears them automatically. If you change a prompt in the code, old cached AI text for HCPs already generated will keep being served until you clear that cache by hand.

**⚠️ Restarting the server does NOT clear any cache.** Every cache is reloaded from its disk file on startup — if the file still has unexpired/uncleared entries, they come right back after a restart exactly as before. Restart and "fresh data" are unrelated; you must explicitly clear the cache to force new data.

**To clear caches — read this before running:**
```bash
cd repstream/backend

# Clears ALL 4 caches at once (response cache + all 3 AI-generation caches)
python scripts/clear_cache.py

# Narrower options:
python scripts/clear_cache.py --expired         # response cache: only entries past their TTL; AI caches untouched
python scripts/clear_cache.py --response-only   # only the response cache, skip the 3 AI-generation caches
python scripts/clear_cache.py --ai-only         # only the 3 AI-generation caches, skip the response cache

# Clears a LIVE running server's response-cache memory immediately, no restart needed
# (only covers the response cache — the AI caches have no live-clear endpoint yet)
curl -X POST http://localhost:8000/admin/cache/clear
```

**Important**: `scripts/clear_cache.py` only touches the **disk files**. If the backend server is already running, it holds its own in-memory copy of every cache loaded at startup — clearing the files does not change what that running process is currently serving. After running the script, either **restart the server** (so it reloads the now-empty files) or, for the response cache specifically, hit `POST /admin/cache/clear` instead (no restart needed, but only affects that one cache).

---

## API Endpoints

All endpoints require header (unless `DEV_SKIP_AUTH=True`):
```
Authorization: Bearer <token>
```

### Action Center — Active Alerts (`/api/v1/action-center`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/alerts?featured=false` | Full active alerts (competitive, payer, HCP awareness sections) |
| GET | `/alerts/summary` | KPI tiles only |
| POST | `/detect` | Run ML detection pipeline manually |
| POST | `/alerts/{alert_id}/enrich` | Re-run GPT-4o enrichment for one alert |
| GET | `/hcp-awareness` | HCP awareness monitoring (score trend, declining HCPs) |
| GET | `/competitive-intel` | Competitive intelligence signals |
| GET | `/payer-access` | Payer formulary access list (tier_current/tier_previous, view_action_plan) |

### Territory Prioritization (`/api/v1/territory`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/summary` | Territory KPI tiles |
| GET | `/hcp-list` | Ranked HCP list with per-HCP GPT-4o insight + embedded view_profile |
| GET | `/hcp/{hcp_id}/insight` | On-demand insight regeneration for one HCP |
| GET | `/hcp/{hcp_id}/profile` | Full HCP profile fields |

### New Writer Identification (`/api/v1/new-writers`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/candidates?territory_id=...` | Non-writer candidates with peer match %, top-5 in-class Rx, and embedded `approach_brief` (AI outreach email) |
| POST | `/{hcp_id}/approach-brief` | On-demand approach-brief regeneration |

### Objection Handler (`/api/v1/objections`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/list` | Ranked objections with frequency |
| GET | `/{objection_id}/response` | MLR-approved response + real supporting materials |
| POST | `/{objection_id}/add-to-call-prep` | Add objection response to call prep |

### App-level

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check (no auth) |
| POST | `/admin/cache/clear` | Clear the live server's in-memory response cache |
| GET | `/api/v1/resources/{filename}` | Download a real payer-access document (`.docx`) |

---

## Example Response — Active Alerts (`GET /api/v1/action-center/alerts`)

```json
{
  "summary": { "...": "KPI tile + banner data" },
  "active_alerts": {
    "competitive_alerts": [
      {
        "alert_type": "competitive",
        "alert_id": "AL-001",
        "ai_severity": "CRITICAL",
        "ai_detection_method": "ANOMALY_DETECTION",
        "detected_at": "2026-04-28 08:15",
        "title": "Competitive script shift in cardiology segment",
        "description": "...",
        "ai_affected_hcp_count": 23,
        "ai_territory_reach": "3/12",
        "ai_rx_risk": "High",
        "ai_icd10_codes_affected": [ { "code": "I50.9", "label": "Heart Failure", "hcp_count": 12 } ],
        "ai_prescribing_drift_note": "...",
        "ai_counter_script": "...",
        "ai_supporting_materials": [ { "title": "APEX Trial Summary", "sku": "APEX-2024-01" } ],
        "recommended_actions": ["Deploy to Field", "View Affected HCPs", "Dismiss"],
        "view_affected_hcp": [ { "hcp_id": "...", "name": "...", "specialty": "...", "city": "...", "state": "..." } ],
        "deploy_to_field": [ { "rep_name": "...", "rep_email": "...", "territory_id": "...", "affected_hcps": ["..."] } ]
      }
    ],
    "payer_alerts": [
      {
        "alert_type": "payer",
        "alert_id": "PAYER-19498",
        "ai_severity": "MEDIUM",
        "title": "Payer formulary update — MM INDUSTRIES Tier change",
        "ai_affected_hcp_count": 8,
        "ai_territory_reach": "156000",
        "ai_rx_risk": "Medium",
        "recommended_actions": ["View HCP List", "Access Resources", "Acknowledge"],
        "view_hcp_list": [ { "name": "..." } ],
        "resources": [ { "title": "Patient Assistance Program (PAP) Enrollment Form", "url": "/api/v1/resources/1_PAP_Enrollment_Form_Template.docx" } ],
        "tier_change": { "from": "Tier 2", "to": "Tier 3" }
      }
    ],
    "hcp_awareness_alerts": [
      {
        "alert_type": "hcp_awareness",
        "alert_id": "AL-003",
        "ai_severity": "HIGH",
        "title": "HCP engagement declining — 6 prescribers showing gradual drift",
        "recommended_actions": ["Schedule Calls", "Review Later"]
      }
    ]
  }
}
```

> Alerts are plain arrays (no `alert_1`/`alert_2` wrapper keys). `payer_alerts` only ever includes alerts with a real `tier_change` sourced from `insight360_payer_access` — alerts with no source tier data are excluded rather than shown with a `null` tier_change. `deploy_to_field` is only meaningful when `"Deploy to Field"` appears in that alert's `recommended_actions`.

---

## ML Models

| Model | Library | File saved | Detects |
|---|---|---|---|
| IsolationForest | `scikit-learn` | `isolation_forest.pkl` | Sudden competitive Rx shift (fallback path only) |
| StandardScaler | `scikit-learn` | `scaler.pkl` | Feature normalization |
| Linear Regression | `numpy.polyfit` | part of `detected_alerts.pkl` | Gradual HCP drift (fallback path only) |
| GPT-4o | `openai` | no file (API call, disk-cached) | All language: titles, scripts, insights, outreach emails |

> Active Alerts reads real pre-computed rows from `insight360_active_alerts` first — the ML pipeline above is a fallback used only if that table is empty or Synapse is unreachable.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Yes | Azure Synapse connection |
| `HUB_SCHEMA`, `DS_SCHEMA` | Yes | Synapse schema names (default `hub_insight360` / `ds_hub_syndb`) |
| `OPENAI_API_KEY` | Yes (unless `LLM_STUB_MODE=True`) | GPT-4o API key |
| `JWT_SECRET` | Yes | JWT signing secret |
| `RESPONSE_CACHE_TTL_MINUTES` | No | Default `1440` (24h). How long GET responses are cached — see [Response Caching](#response-caching-no-redis) |
| `REDIS_URL` | No | Only used by Celery / the legacy `app/utils/cache.py`, not the response cache |
| `LLM_STUB_MODE` | No | `True` = skip GPT-4o calls, return stub text (no API key needed, local dev) |
| `DEV_SKIP_AUTH` | No | `True` = skip JWT auth, auto-login as `REP001` (**local dev only, never production**) |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `DB_PASSWORD` error | Add it to `.env` file |
| `OPENAI_API_KEY` error | Add key to `.env` or set `LLM_STUB_MODE=True` |
| ML models slow on first call | Run `python scripts/train_ml_models.py` first |
| Auth errors on API calls | Run `python scripts/generate_test_token.py`, or set `DEV_SKIP_AUTH=True` for local dev |
| `.pkl` files stale / wrong data | Run `python scripts/train_ml_models.py` again |
| Seeing `log.warning(...)` messages in the terminal | That's Python's `logging` module, not `print()` — it's expected output for handled/fallback errors (e.g. a query hitting a non-existent column falls back gracefully but still logs a warning) |
| A response looks stale / not reflecting a recent DB or code change | Some cache is serving an old copy — run `python scripts/clear_cache.py` (clears all 4 caches on disk), then restart the server (or use `POST /admin/cache/clear` for just the response cache, no restart needed) |
| `ImportError` on startup mentioning `app.utils.response_cache` | That file is source code, not a cache data file — if it's missing, restore it with `git checkout HEAD -- backend/app/utils/response_cache.py` |
| `[WinError 10013]` / port already in use | Another process (often a leftover `--reload` process) is bound to port 8000 — find and stop it, or use a different `--port` |

---

## Known Limitations (not yet production-ready)

- `DEV_SKIP_AUTH=True` in the current `.env` bypasses all JWT auth — must be `False` before any real deployment.
- `docker-compose.yml` and the `Dockerfile` reference `app.main:app` as the entry point — the real entry point is `main:app` (at `backend/main.py`, not `backend/app/main.py`). This needs fixing before Docker will actually start.
- The Synapse connection requires the deploying environment's IP to be allow-listed on the Azure firewall.
- All AI/response caches are local JSON files on disk — they won't work correctly if the backend ever runs as multiple replicas/workers (each would have its own separate cache, and concurrent writes to the same file aren't cross-process-safe).

---

## Docker (optional — not currently verified working, see Known Limitations)

```bash
cd repstream
docker-compose up --build
```
