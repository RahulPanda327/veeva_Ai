# RepStream — Testing Guide

There are four ways to test the 3 modules, depending on what you have available.

---

## Path A — Unit tests only (no DB, no Docker, no OpenAI key needed)

Tests all service-layer business logic with mocked database responses.

```bash
cd backend

# Create virtual env (one time)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run a specific module
pytest tests/test_territory_prioritization.py -v
pytest tests/test_new_writer_id.py -v
pytest tests/test_objection_handler.py -v
```

Expected output: **30+ tests passing** covering Rx trend calc, priority tiers, ICD-10 matching, objection frequency labels, success rate formulas, and MLR lookup.

---

## Path B — Full API + Swagger UI (requires Docker + PostgreSQL)

This tests the real API endpoints end-to-end with seed data.

### Step 1 — Start the infrastructure

```bash
# From repstream/ root
docker compose up db redis -d      # start only DB + Redis first
```

### Step 2 — Configure .env for dev mode

```bash
cd backend
copy .env.example .env
```

Edit `backend/.env` — minimum required values:

```env
DATABASE_URL=postgresql+psycopg2://repstream_user:repstream_secret@localhost:5432/repstream_db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=dev-secret-key-change-me

# Enable dev shortcuts (no OpenAI key needed, no JWT needed)
DEV_SKIP_AUTH=true
LLM_STUB_MODE=true
```

### Step 3 — Seed the database

```bash
cd backend
python scripts/seed_demo_data.py
```

Output confirms: 8 HCPs, 5 objections, 4 transcripts, 3 peer matches seeded.

### Step 4 — Start the FastAPI server

```bash
uvicorn app.main:app --reload --port 8000
```

### Step 5 — Open Swagger UI

Go to **http://localhost:8000/api/docs**

Because `DEV_SKIP_AUTH=true`, all endpoints work without a token.

#### Test Module 1 — Territory Prioritization

| Endpoint | Click | Expected |
|---|---|---|
| `GET /api/v1/territory/summary` | Try it out → Execute | 8 HCPs, 3 HIGH, 3 MEDIUM, 1 LOW, target=2 |
| `GET /api/v1/territory/hcp-list` | Try it out → Execute | 8 cards ranked HIGH→MEDIUM→LOW with Rx trends |
| `GET /api/v1/territory/hcp/{hcp_id}/insight` | hcp_id=`HCP001` | AI insight text (stub or real) |

#### Test Module 2 — New Writer ID

| Endpoint | Expected |
|---|---|
| `GET /api/v1/new-writers/candidates` | 3 candidates: HCP002, HCP005, HCP008 with peer_match_pct and ICD-10 codes |
| `POST /api/v1/new-writers/HCP002/approach-brief` | 2-sentence warm outreach brief for Dr. Robert Chen |

#### Test Module 3 — Objection Handler

| Endpoint | Expected |
|---|---|
| `GET /api/v1/objections/list` | 5 objections: COVERAGE (HIGH, 12 calls), COST (HIGH, 9), COMPETITOR (MEDIUM, 7)… |
| `GET /api/v1/objections/OBJ-001/response` | MLR response for coverage objection, SKU ZPP-40MG-40CAP, 58% success |
| `POST /api/v1/objections/OBJ-001/add-to-call-prep` | Body: `{"rep_id":"REP001"}` → success: true |

---

## Path C — Frontend UI testing (full stack)

### Option 1: Vite dev server (hot reload)

```bash
# Terminal 1: backend
cd backend && uvicorn app.main:app --reload

# Terminal 2: frontend
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**

The Vite proxy forwards `/api/*` to the backend automatically.

**Set a token in browser localStorage** (needed when `DEV_SKIP_AUTH=false`):

```js
// In browser DevTools console:
localStorage.setItem('repstream_token', '<paste token from generate_test_token.py>')
localStorage.setItem('repstream_rep_id', 'REP001')
```

Or run with `DEV_SKIP_AUTH=true` to skip this step entirely.

### Option 2: Full Docker Compose

```bash
docker compose up --build
```

Open **http://localhost** (nginx serves the built React app).

---

## Path D — Real OpenAI key (optional)

To get real GPT-4o insights instead of stub text:

```env
# In backend/.env
OPENAI_API_KEY=sk-...
LLM_STUB_MODE=false        # ← change this
DEV_SKIP_AUTH=true         # keep for easy testing
```

Restart the server. The `GET /api/v1/territory/hcp/{hcp_id}/insight` and
`POST /api/v1/new-writers/{hcp_id}/approach-brief` endpoints will now call
GPT-4o and cache the result in Redis for 24h / 1h respectively.

---

## Generate a JWT token (when DEV_SKIP_AUTH=false)

```bash
cd backend
python scripts/generate_test_token.py
# Options: --rep-id REP001 --territory TERR-001 --hours 48
```

Paste the printed token into:
- Swagger UI → Authorize button (just the token, no "Bearer" prefix)
- Browser DevTools → `localStorage.setItem('repstream_token', '<token>')`
- curl → `-H "Authorization: Bearer <token>"`

---

## curl quick-test (all 3 modules)

```bash
TOKEN=$(cd backend && python scripts/generate_test_token.py 2>/dev/null | grep -A1 "below" | tail -1)

# Module 1
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/territory/summary | python -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/territory/hcp-list | python -m json.tool

# Module 2
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/new-writers/candidates | python -m json.tool
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     http://localhost:8000/api/v1/new-writers/HCP002/approach-brief | python -m json.tool

# Module 3
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/objections/list | python -m json.tool
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/objections/OBJ-001/response | python -m json.tool
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"rep_id":"REP001"}' \
     http://localhost:8000/api/v1/objections/OBJ-001/add-to-call-prep | python -m json.tool
```

---

## Expected seed data summary

| Module | What you'll see |
|---|---|
| **Territory** | HCP001 Dr. Jane Smith — HIGH (50% trend), HCP003 Dr. Alice Patel — HIGH (above P75), HCP007 Dr. Emily Walsh — HIGH (30% trend), HCP006 Dr. David Nguyen — LOW (-36% trend) |
| **New Writers** | HCP002 Dr. Robert Chen (82.5% peer match, ICD-10: K86.1), HCP005 Dr. Sarah Kim (67% peer match), HCP008 Dr. James Brown (45% peer match) |
| **Objections** | COVERAGE 12 calls HIGH, COST 9 calls HIGH, COMPETITOR 7 calls MEDIUM, EFFICACY 4 calls MEDIUM, AWARENESS 3 calls MEDIUM |
