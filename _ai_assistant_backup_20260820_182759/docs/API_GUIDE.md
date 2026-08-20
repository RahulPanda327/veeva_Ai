# DataStream Chatbot API — Postman & Operations Guide

> **Base URL:** `http://localhost:8000`  
> **Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)  
> **ReDoc:** `http://localhost:8000/redoc`

---

## Table of Contents

1. [Quick Start — How to Run the Server](#1-quick-start)
2. [Postman Environment Setup](#2-postman-environment-setup)
3. [Authentication](#3-authentication)
4. [Health Check](#4-health-check)
5. [Chat Endpoints](#5-chat-endpoints)
6. [Session Management](#6-session-management)
7. [Model & Scenario Management](#7-model--scenario-management)
8. [Documents (Vector Store)](#8-documents-vector-store)
9. [Database — Scenario 4](#9-database--scenario-4-azure-synapse)
10. [Charts](#10-charts)
11. [Common Workflows](#11-common-workflows)
12. [Scenario 4 — Database Q&A Deep-Dive](#12-scenario-4-deep-dive)
13. [Terminal Client (CLI)](#13-terminal-client-cli)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Quick Start

### Prerequisites
- Python 3.11+
- ODBC Driver 17 for SQL Server installed (for Scenario 4)
- All Python packages installed

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Configure `.env`
Open `.env` and fill in the required values:

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | For S1/S2 | Your Groq API key |
| `OPENAI_API_KEY` | Optional | OpenAI alternative |
| `ANTHROPIC_API_KEY` | Optional | Anthropic alternative |
| `ADMIN_USERNAME` | Yes | Admin login (default: `admin`) |
| `ADMIN_PASSWORD` | Yes | Admin password (default: `admin`) |
| `JWT_SECRET_KEY` | Yes | Change to a long random string in production |
| `PINECONE_API_KEY` | For S3 | Pinecone vector DB key |
| `DB_HOST` | For S4 | `averitassynprdwks.sql.azuresynapse.net` |
| `DB_NAME` | For S4 | `averitas_syn_prd_db` |
| `DB_USER` | For S4 | Your Synapse username |
| `DB_PASSWORD` | For S4 | Your Synapse password |
| `ACTIVE_SCENARIO` | Yes | 1=LLM, 2=LLM+Rules, 3=Embeddings, 4=Database |

### Step 3 — Start the server
```bash
# Development (auto-reload on file changes)
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Or use the main entrypoint
python main.py
```

### Step 4 — Verify it's running
```
GET http://localhost:8000/health
```
Expected response:
```json
{
  "status": "healthy",
  "active_scenario": 1,
  "provider": "groq",
  "model": "llama3-8b-8192"
}
```

> **Note:** First startup may take 30-60 seconds if PINECONE_API_KEY is set — it downloads the all-MiniLM-L6-v2 sentence transformer model (~90 MB). Subsequent starts are instant.

---

## 2. Postman Environment Setup

### Create a Postman Environment named `DataStream Local`

| Variable | Initial Value | Description |
|---|---|---|
| `base_url` | `http://localhost:8000` | Server address |
| `token` | (empty — auto-filled by login script) | JWT Bearer token |
| `session_id` | (empty — auto-filled by chat) | Active session UUID |

### Auto-set token after login

In the Login request, go to the **Tests** tab and paste:
```javascript
const data = pm.response.json();
pm.environment.set("token", data.access_token);
console.log("Token saved:", data.access_token.substring(0, 30) + "...");
```

### Authorization header (all protected requests)

In each request, go to the **Authorization** tab:
- Type: `Bearer Token`
- Token: `{{token}}`

Or add a **Collection-level** auth so all requests inherit it automatically.

---

## 3. Authentication

### POST `/auth/login`

Get a JWT token. All other endpoints require this token.

**Request Body:**
```json
{
  "username": "admin",
  "password": "admin",
  "client_id": "postman"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

> Token expires after `JWT_EXPIRY_HOURS` (default 24h). Re-login to refresh.

---

## 4. Health Check

### GET `/health`
No auth required. Use to verify the server is running.

**Response:**
```json
{
  "status": "healthy",
  "active_scenario": 1,
  "provider": "groq",
  "model": "llama3-8b-8192"
}
```

---

## 5. Chat Endpoints

### POST `/chat` — Send a message (blocking)

**Headers:** `Authorization: Bearer {{token}}`

**Request Body (new conversation):**
```json
{
  "message": "What files are scheduled for today?"
}
```

**Request Body (resume existing session):**
```json
{
  "message": "Show me the last 7 days of load history",
  "session_id": "{{session_id}}"
}
```

**Optional fields:**
```json
{
  "message": "Your question here",
  "session_id": "uuid-of-existing-session",
  "system_prompt": "You are a helpful data analyst.",
  "metadata_filter": {"category": {"$eq": "support"}}
}
```

**Response:**
```json
{
  "response": "Here are the files scheduled for today...",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "scenario": 1,
  "provider": "groq",
  "model": "llama3-8b-8192",
  "cached": false,
  "rule_matched": null,
  "retrieved_docs": 0,
  "cosine_scores": [],
  "metadata": {}
}
```

**Scenario 4 response — metadata is populated:**
```json
{
  "response": "**Files scheduled today** — 12 rows\n| file_name | ...",
  "scenario": 4,
  "provider": "db",
  "model": "synapse:averitas_syn_prd_db",
  "metadata": {
    "source": "template",
    "intent": "scheduled_today",
    "sql": "SELECT TOP 100 file_name, schedule_time...",
    "columns": ["file_name", "schedule_time", "status"],
    "row_count": 12,
    "rows": [],
    "chart": {
      "kind": "bar",
      "path": "charts/chart_20260520_153045.png",
      "png_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
    }
  }
}
```

---

### POST `/chat/stream` — Send a message (Server-Sent Events)

Real-time streaming response. Each line is a `data:` SSE event.

**Request Body:** Same as `/chat`

**Response stream:**
```
data: {"type": "chunk", "content": "Here are"}
data: {"type": "chunk", "content": " the files scheduled today..."}
data: {"type": "meta", "session_id": "550e8400...", "scenario": 1, "provider": "groq"}
data: [DONE]
```

> **Postman tip:** Enable "Save response" and set response type to `text` to see SSE events.

---

### DELETE `/chat/{session_id}/context`

Clears the LLM context window (in-memory history) without deleting the session from DB.

**Response:**
```json
{
  "message": "Context window cleared; history preserved in DB",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### GET `/chat/memory/stats`

**Response:**
```json
{
  "active_sessions": 3,
  "cache_enabled": true,
  "cache_size": 12,
  "cache_max": 100,
  "cache_ttl_seconds": 3600,
  "memory_window_size": 15
}
```

---

## 6. Session Management

### GET `/sessions`

List all sessions for the logged-in user.

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "What files are scheduled today?",
    "scenario": 4,
    "message_count": 6,
    "created_at": "2026-05-20T10:00:00",
    "updated_at": "2026-05-20T10:05:00"
  }
]
```

---

### GET `/sessions/{session_id}`

Get full session including all messages.

**Response:**
```json
{
  "id": "550e8400...",
  "title": "What files are scheduled today?",
  "scenario": 4,
  "message_count": 6,
  "messages": [
    {"role": "user", "content": "What files are scheduled today?", "created_at": "..."},
    {"role": "assistant", "content": "**Files scheduled today**...", "created_at": "..."}
  ]
}
```

---

### PATCH `/sessions/{session_id}` — Rename

**Request Body:**
```json
{
  "title": "My Custom Conversation Title"
}
```

---

### DELETE `/sessions/{session_id}` — Delete

Returns `204 No Content`

---

## 7. Model & Scenario Management

### GET `/model/status`

**Response:**
```json
{
  "active_scenario": 1,
  "scenario_description": "LLM Only — cloud API (Groq / OpenAI / Anthropic)",
  "active_provider": "groq",
  "active_model": "llama3-8b-8192",
  "temperature": 0.7,
  "max_tokens": 1024,
  "memory_window_size": 15,
  "cache_enabled": true,
  "cosine_similarity_threshold": 0.7,
  "available_scenarios": {
    "1": "LLM Only — cloud API",
    "2": "LLM + Rule-Based — rules first, LLM fallback",
    "3": "Embedding + Rule-Based — local, no LLM cost",
    "4": "Database Q&A — Azure Synapse (template + optional LLM SQL)"
  }
}
```

---

### POST `/model/switch`

Switch scenario, provider, model, or tune parameters **without restarting the server**.

**Switch to Scenario 4 (Database):**
```json
{ "scenario": 4 }
```

**Switch to OpenAI GPT-4o:**
```json
{
  "scenario": 1,
  "provider": "openai",
  "model": "gpt-4o",
  "temperature": 0.5
}
```

**Switch to Groq Llama 70B:**
```json
{
  "scenario": 2,
  "provider": "groq",
  "model": "llama-3.3-70b-versatile"
}
```

**Tune parameters only:**
```json
{
  "memory_window_size": 20,
  "cosine_similarity_threshold": 0.75
}
```

**Response:**
```json
{
  "message": "Updated: scenario, provider, model",
  "changed_fields": ["scenario", "provider", "model"],
  "previous": {"scenario": 1, "provider": "groq", "model": "llama3-8b-8192"},
  "current": {"scenario": 4, "provider": "openai", "model": "gpt-4o"}
}
```

---

## 8. Documents (Vector Store)

> For Scenario 3 (Embedding + Rules). Requires `PINECONE_API_KEY`.

### POST `/documents` — Upload one document

```json
{
  "text": "The copay file loads every day at 6 AM.",
  "metadata": {
    "category": "support",
    "source": "ops-handbook"
  }
}
```

### POST `/documents/seed` — Bulk upload

```json
{
  "documents": [
    {"text": "First document...", "metadata": {"category": "faq"}},
    {"text": "Second document...", "metadata": {"category": "support"}}
  ]
}
```

### DELETE `/documents/{doc_id}` — Remove a document

---

## 9. Database — Scenario 4 (Azure Synapse)

### GET `/db/test` — Ping Synapse

**Success:**
```json
{ "ok": true, "version": "Microsoft SQL Azure (RTM) - 12.0.2000.8" }
```

**Failure (creds not set):**
```json
{ "ok": false, "error": "Database is not fully configured. Set DB_HOST, DB_NAME, DB_USER, DB_PASSWORD in .env." }
```

---

### GET `/db/templates` — List all Q&A templates

**Response:**
```json
{
  "count": 19,
  "templates": [
    {
      "intent": "scheduled_today",
      "description": "Files scheduled to run today",
      "example_questions": ["Which files are scheduled today?", "What jobs run today?"],
      "chart_hint": {"kind": "bar", "x": "file_name", "y": "schedule_count"}
    },
    {
      "intent": "load_history_days",
      "description": "Load history for last N days",
      "example_questions": ["Show last 7 days load history for copay"],
      "chart_hint": {"kind": "line", "x": "load_date", "y": "row_count"}
    }
  ]
}
```

---

### GET `/db/schema` — LLM schema context

Returns the full table schema used when generating SQL via LLM fallback.

---

### POST `/db/sql` — Execute read-only SQL directly

```json
{
  "sql": "SELECT TOP 10 file_name, status, load_date FROM HUB_MD.dbo.FILE_LOAD_HISTORY ORDER BY load_date DESC",
  "params": []
}
```

**With parameterized values:**
```json
{
  "sql": "SELECT TOP 50 * FROM HUB_MD.dbo.FILE_SCHEDULE WHERE file_name = ?",
  "params": ["copay_daily"]
}
```

**Response:**
```json
{
  "columns": ["file_name", "status", "load_date"],
  "rows": [
    {"file_name": "copay_daily", "status": "SUCCESS", "load_date": "2026-05-20T06:00:00"}
  ],
  "row_count": 1
}
```

> Write statements (INSERT/UPDATE/DELETE/DROP/etc.) are blocked automatically.

---

## 10. Charts

### GET `/charts/{filename}` — Serve generated chart PNG

```
GET /charts/chart_20260520_153045.png
```

Returns: raw `image/png` — view in Postman's Preview tab or download.

The filename is returned in `metadata.chart.path` from every Scenario 4 chat response.

---

## 11. Common Workflows

### Workflow A — Standard Chat (Scenario 1)
```
1. POST /auth/login                                    → save token
2. POST /chat {"message": "Hello"}                    → save session_id
3. POST /chat {"message": "...", "session_id": "..."}  → continue
4. GET  /sessions                                      → list conversations
5. DELETE /chat/{id}/context                           → clear context window
```

### Workflow B — Database Q&A (Scenario 4)
```
1. POST /auth/login                                    → save token
2. GET  /db/test                                       → confirm Synapse reachable
3. GET  /db/templates                                  → browse 19 templates
4. POST /model/switch {"scenario": 4}                  → activate database mode
5. POST /chat {"message": "Which files failed yesterday?"}
         → response.metadata.sql shows the SQL used
         → response.metadata.chart.path shows chart file
6. GET  /charts/chart_20260520_153045.png              → view the chart
```

### Workflow C — Compare Models Live
```
1. POST /model/switch {"scenario": 1, "provider": "groq", "model": "llama-3.1-8b-instant"}
2. POST /chat {"message": "Explain ETL pipelines"}    → note response
3. POST /model/switch {"provider": "openai", "model": "gpt-4o"}
4. POST /chat {"message": "Explain ETL pipelines"}    → compare quality
```

---

## 12. Scenario 4 Deep-Dive

### Question Routing Flow
```
User question
      |
      v
Template matcher (regex + keywords)
      |-- Match found? --> Execute parameterized SQL --> Format + Chart
      |
      |-- No match
      |
      v
LLM fallback enabled?
      |-- YES --> LLM generates SQL --> Read-only validator --> Execute if safe
      |-- NO  --> "I couldn't match this question" message
```

### Built-in Template Questions

| Intent | Example Questions |
|---|---|
| `scheduled_today` | "Which files are scheduled today?", "What jobs run today?" |
| `load_history_days` | "Show last 7 days load history for copay", "14 day trend" |
| `failed_files` | "Which files failed yesterday?", "Show failures for last 3 days" |
| `file_status` | "What is the status of copay_daily?", "Check claims_feed" |
| `long_running` | "Which jobs took more than 2 hours?", "Slowest files today" |
| `row_count_trend` | "Row count trend for copay last 30 days" |
| `files_by_status` | "How many files succeeded vs failed today?" |
| `schedule_summary` | "Full schedule summary for this week" |

### Chart Auto-Detection Logic

| Data shape | Chart type |
|---|---|
| Date column + numeric column | Line chart (trends) |
| Category + numeric column | Bar chart |
| Status/category only | Bar chart (count per value) |
| Less than 2 rows or all nulls | No chart generated |

### Safety Rules
- All user parameters bind via `?` placeholders (SQL injection proof)
- Write statements blocked: INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE, EXEC, GRANT, REVOKE, BACKUP, RESTORE, MERGE
- Results capped at `DB_MAX_ROWS` (default 1000 rows)
- Connection timeout: `DB_QUERY_TIMEOUT_SECONDS` (default 30s)

---

## 13. Terminal Client (CLI)

```bash
python client.py
```

### Menu Options
```
[1] Chat              — start or resume a conversation
[2] Switch model      — change scenario/provider/model at runtime  
[3] My conversations  — browse, resume, rename, delete sessions
[4] Config & stats    — current settings + memory stats
[5] Clear context     — reset LLM window (history preserved)
[6] Exit
```

### In-chat Commands

| Command | Action |
|---|---|
| `back` or `menu` | Return to main menu |
| `newsession` | Start a fresh conversation |
| `stream` | Toggle streaming mode on/off |

### Scenario 4 DB Output in Terminal
```
  You: Which files failed yesterday?

  Bot: **Files that failed yesterday** — 3 rows
  | file_name   | status | error_message      |
  |-------------|--------|--------------------|
  | claims_feed | FAILED | Connection timeout |

  ┌─ DB metadata (template)─
  │ Intent    : failed_files
  │ Rows      : 3
  │ SQL       : SELECT TOP 100 file_name, status, error_message FROM HUB_MD...
  │ Chart     : charts/chart_20260520_153045.png  [bar]
  └──────────────────────────────────────────────────
```

---

## 14. Troubleshooting

### Server won't start / very slow startup
**Cause:** First-time download of sentence-transformer model (~90MB).  
**Fix:** Wait 1-2 minutes. If you don't use Scenario 3, remove `PINECONE_API_KEY` from `.env` to skip encoder warmup entirely.

### `401 Unauthorized` on every request
**Fix:** Re-run the login request. Make sure the `token` environment variable is updated in Postman.

### Scenario 4 returns "not configured"
**Fix:** Open `.env` and set all four DB variables:
```
DB_HOST=averitassynprdwks.sql.azuresynapse.net
DB_NAME=averitas_syn_prd_db
DB_USER=your-actual-username
DB_PASSWORD=your-actual-password
```
Then call `GET /db/test` to verify.

### Port 8000 already in use
```powershell
# Find what is using port 8000
netstat -ano | findstr :8000

# Kill by PID
taskkill /PID 12345 /F
```

### ReadOnlyViolation on /db/sql
Your SQL contains a write statement. Only SELECT/WITH are allowed.

---

## API Quick Reference Card

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | No | Get JWT token |
| `GET` | `/health` | No | Server health check |
| `POST` | `/chat` | Yes | Send message (blocking) |
| `POST` | `/chat/stream` | Yes | Send message (SSE streaming) |
| `DELETE` | `/chat/{id}/context` | Yes | Clear LLM context window |
| `GET` | `/chat/memory/stats` | Yes | Cache and memory stats |
| `GET` | `/sessions` | Yes | List all sessions |
| `GET` | `/sessions/{id}` | Yes | Get session with full history |
| `PATCH` | `/sessions/{id}` | Yes | Rename session |
| `DELETE` | `/sessions/{id}` | Yes | Delete session |
| `GET` | `/model/status` | Yes | Current runtime config |
| `POST` | `/model/switch` | Yes | Switch scenario/model live |
| `POST` | `/documents` | Yes | Upload doc to vector store |
| `POST` | `/documents/seed` | Yes | Bulk upload documents |
| `DELETE` | `/documents/{id}` | Yes | Remove document |
| `GET` | `/db/test` | Yes | Ping Synapse database |
| `GET` | `/db/templates` | Yes | List 19 SQL templates |
| `GET` | `/db/schema` | Yes | LLM schema context |
| `POST` | `/db/sql` | Yes | Run read-only SQL directly |
| `GET` | `/charts/{filename}` | Yes | Serve chart PNG |

---

*DataStream Chatbot v1.0 — Azure Synapse + Groq/OpenAI/Anthropic + Pinecone*
