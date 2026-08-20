"""
Live integration test — runs against localhost:8000
Usage: python test_api.py
"""
import httpx
import sys

BASE = "http://localhost:8000"
results = []


def log(label, ok, detail=""):
    sym = "[PASS]" if ok else "[FAIL]"
    results.append((label, ok, detail))
    suffix = f"  ->  {detail}" if detail else ""
    print(f"{sym} {label}{suffix}")


# ── 1. Health ──────────────────────────────────────────────────────────────────
r = httpx.get(f"{BASE}/health", timeout=5)
log("GET /health", r.status_code == 200, r.json().get("status", ""))

# ── 2. Login ───────────────────────────────────────────────────────────────────
r = httpx.post(
    f"{BASE}/auth/login",
    json={"username": "admin", "password": "admin", "client_id": "api"},
    timeout=5,
)
log(
    "POST /auth/login",
    r.status_code == 200,
    "token received" if "access_token" in r.json() else r.text[:80],
)
token = r.json().get("access_token", "")
H = {"Authorization": f"Bearer {token}"}

# ── 3. Model status ────────────────────────────────────────────────────────────
r = httpx.get(f"{BASE}/model/status", headers=H, timeout=5)
d = r.json()
log(
    "GET /model/status",
    r.status_code == 200,
    f"scenario={d.get('active_scenario')} provider={d.get('active_provider')}",
)

# ── 4. Chat — Scenario 1 ───────────────────────────────────────────────────────
r = httpx.post(
    f"{BASE}/chat",
    json={"message": "Hello! What can you help me with?"},
    headers=H,
    timeout=30,
)
d = r.json()
log(
    "POST /chat (S1 new session)",
    r.status_code == 200,
    f"session={str(d.get('session_id',''))[:8]}... scenario={d.get('scenario')}",
)
session_id = d.get("session_id", "")

# ── 5. Resume session ──────────────────────────────────────────────────────────
r = httpx.post(
    f"{BASE}/chat",
    json={"message": "What did I just ask you?", "session_id": session_id},
    headers=H,
    timeout=30,
)
log(
    "POST /chat (resume session)",
    r.status_code == 200,
    f"same session={r.json().get('session_id') == session_id}",
)

# ── 6. Chat stream ────────────────────────────────────────────────────────────
chunks = 0
try:
    with httpx.stream(
        "POST",
        f"{BASE}/chat/stream",
        json={"message": "Tell me one fun fact", "session_id": session_id},
        headers=H,
        timeout=30,
    ) as resp:
        for line in resp.iter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                chunks += 1
    log("POST /chat/stream (SSE)", resp.status_code == 200, f"{chunks} SSE events")
except Exception as e:
    log("POST /chat/stream (SSE)", False, str(e)[:60])

# ── 7. Sessions list ───────────────────────────────────────────────────────────
r = httpx.get(f"{BASE}/sessions", headers=H, timeout=5)
log("GET /sessions", r.status_code == 200, f"{len(r.json())} sessions returned")

# ── 8. Session detail ─────────────────────────────────────────────────────────
if session_id:
    r = httpx.get(f"{BASE}/sessions/{session_id}", headers=H, timeout=5)
    d = r.json()
    log(
        "GET /sessions/{id}",
        r.status_code == 200,
        f"{d.get('message_count', 0)} messages in session",
    )

# ── 9. Memory stats ────────────────────────────────────────────────────────────
r = httpx.get(f"{BASE}/chat/memory/stats", headers=H, timeout=5)
d = r.json()
log(
    "GET /chat/memory/stats",
    r.status_code == 200,
    f"active={d.get('active_sessions')} cache={d.get('cache_enabled')}",
)

# ── 10. Switch to Scenario 4 ───────────────────────────────────────────────────
r = httpx.post(f"{BASE}/model/switch", json={"scenario": 4}, headers=H, timeout=5)
log(
    "POST /model/switch (scenario=4)",
    r.status_code == 200,
    r.json().get("message", ""),
)

# ── 11. DB templates ──────────────────────────────────────────────────────────
r = httpx.get(f"{BASE}/db/templates", headers=H, timeout=5)
d = r.json()
log(
    "GET /db/templates",
    r.status_code == 200,
    f"{d.get('count', 0)} templates loaded",
)

# ── 12. DB schema ─────────────────────────────────────────────────────────────
r = httpx.get(f"{BASE}/db/schema", headers=H, timeout=5)
d = r.json()
log(
    "GET /db/schema",
    r.status_code == 200,
    "schema context present" if d.get("schema_context") else "empty",
)

# ── 13. DB connectivity test ──────────────────────────────────────────────────
r = httpx.get(f"{BASE}/db/test", headers=H, timeout=15)
d = r.json()
db_ok = d.get("ok", False)
detail = str(d.get("version", d.get("error", "")))[:80]
log("GET /db/test (Synapse ping)", r.status_code == 200, f"ok={db_ok}  {detail}")

# ── 14. Switch back to Scenario 1 ─────────────────────────────────────────────
r = httpx.post(f"{BASE}/model/switch", json={"scenario": 1}, headers=H, timeout=5)
log("POST /model/switch (back to S1)", r.status_code == 200, r.json().get("message", ""))

# ── 15. Clear context ─────────────────────────────────────────────────────────
if session_id:
    r = httpx.delete(f"{BASE}/chat/{session_id}/context", headers=H, timeout=5)
    log("DELETE /chat/{id}/context", r.status_code == 200, r.json().get("message", "")[:60])

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
passed = sum(1 for _, ok, _ in results if ok)
failed = [(lbl, det) for lbl, ok, det in results if not ok]
print(f"  RESULTS: {passed}/{len(results)} passed")
if failed:
    print("\n  FAILURES:")
    for lbl, det in failed:
        print(f"    • {lbl}: {det}")
print("=" * 60)
sys.exit(0 if not failed else 1)
