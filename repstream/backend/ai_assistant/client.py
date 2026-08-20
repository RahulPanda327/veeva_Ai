"""
DataStream Chatbot — Terminal Client

Reads from .env:
  API_BASE_URL    server address            (default: http://localhost:8000)
  ADMIN_USERNAME  login username
  ADMIN_PASSWORD  login password

JWT structure carried on every request:
  sub         — username
  jti         — unique token ID
  client_id   — "terminal" (set at login)
  token_type  — "access"
  iat / exp   — timestamps

Session flow:
  • New chat   → POST /chat (no session_id) → server returns new UUID
  • Resume     → GET /sessions to pick a past conversation,
                 then POST /chat with that session_id
  • History    → GET /sessions/{id} shows all past messages
  • Delete     → DELETE /sessions/{id}
"""

import json
import os
import sys
from typing import Iterator, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
PASSWORD: str = os.getenv("ADMIN_PASSWORD", "changeme123")

SCENARIO_LABELS: dict[int, str] = {
    1: "LLM Only          (Groq / OpenAI / Anthropic)",
    2: "LLM + Rule-Based  (rules first, LLM fallback)",
    3: "Embedding + Rules (local — no LLM cost)",
    4: "Database Q&A      (Azure Synapse — SQL + charts)",
}

PROVIDER_MODELS: dict[str, list[str]] = {
    "groq":      ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "gemma2-9b-it", "llama-3.2-1b-preview"],
    "openai":    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    "anthropic": ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
}

W = 62   # display width


# ── HTTP client wrapper ─────────────────────────────────────────────────────────

class DataStreamClient:
    def __init__(self):
        self._http = httpx.Client(base_url=BASE_URL, timeout=60.0)
        self.token: Optional[str] = None
        self.jti: Optional[str] = None
        self.client_id: str = "terminal"
        self.session_id: Optional[str] = None   # active session
        self.streaming: bool = True             # toggle via menu

    def login(self) -> bool:
        try:
            r = self._http.post("/auth/login", json={
                "username": USERNAME,
                "password": PASSWORD,
                "client_id": self.client_id,
            })
            r.raise_for_status()
            data = r.json()
            self.token = data["access_token"]
            return True
        except Exception as exc:
            print(f"  Login failed: {exc}")
            return False

    @property
    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    # ── Chat ────────────────────────────────────────────────────────────────────

    def send(self, message: str) -> dict:
        r = self._http.post(
            "/chat",
            json={"request": {"user_query": message, "app_session_id": self.session_id}},
            headers=self._h,
        )
        r.raise_for_status()
        data = r.json()
        resp = data.get("response", {})
        self.session_id = resp.get("chat_session_id") or self.session_id
        # Normalize to the shape chat_loop expects
        return {
            "response": resp.get("output_query", {}).get("answer", ""),
            "session_id": self.session_id,
            "metadata": resp.get("processing_details", {}),
        }

    def send_stream(self, message: str) -> Iterator[dict]:
        """
        POST /chat/stream and yield decoded SSE events.
        Each event is either {"type":"chunk","content":...},
        {"type":"meta",...}, or {"type":"error","detail":...}.
        """
        with self._http.stream(
            "POST",
            "/chat/stream",
            json={"request": {"user_query": message, "app_session_id": self.session_id}},
            headers=self._h,
            timeout=120.0,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    return
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "meta" and event.get("session_id"):
                    self.session_id = event["session_id"]
                yield event

    def clear_context(self) -> bool:
        if not self.session_id:
            return False
        r = self._http.delete(f"/chat/{self.session_id}/context", headers=self._h)
        r.raise_for_status()
        return True

    # ── Sessions ────────────────────────────────────────────────────────────────

    def list_sessions(self) -> list[dict]:
        r = self._http.get("/sessions", headers=self._h)
        r.raise_for_status()
        return r.json()

    def get_session(self, session_id: str) -> dict:
        r = self._http.get(f"/sessions/{session_id}", headers=self._h)
        r.raise_for_status()
        return r.json()

    def delete_session(self, session_id: str) -> bool:
        r = self._http.delete(f"/sessions/{session_id}", headers=self._h)
        r.raise_for_status()
        return True

    def rename_session(self, session_id: str, title: str) -> bool:
        r = self._http.patch(
            f"/sessions/{session_id}",
            json={"title": title},
            headers=self._h,
        )
        r.raise_for_status()
        return True

    # ── Model management ────────────────────────────────────────────────────────

    def status(self) -> dict:
        r = self._http.get("/model/status", headers=self._h)
        r.raise_for_status()
        return r.json()

    def switch(self, **kwargs) -> dict:
        r = self._http.post("/model/switch", json=kwargs, headers=self._h)
        r.raise_for_status()
        return r.json()

    def memory_stats(self) -> dict:
        r = self._http.get("/chat/memory/stats", headers=self._h)
        r.raise_for_status()
        return r.json()

    def close(self):
        self._http.close()


# ── UI helpers ──────────────────────────────────────────────────────────────────

def bar(char="─") -> str:
    return char * W


def _pick(prompt: str, options: list[str]) -> Optional[int]:
    for i, o in enumerate(options, 1):
        print(f"    [{i}] {o}")
    raw = input(f"  {prompt}: ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return int(raw) - 1
    return None


def _fmt_date(iso: str) -> str:
    return iso[:16].replace("T", " ")


# ── Banners ─────────────────────────────────────────────────────────────────────

def print_banner():
    print("\n" + bar("═"))
    print("       DataStream AI Chatbot  ·  Terminal Client")
    print(bar("═"))


def print_main_menu(st: dict, session_id: Optional[str]):
    sc  = st.get("active_scenario", "?")
    prv = st.get("active_provider", "?").upper()
    mdl = st.get("active_model", "?")
    lbl = SCENARIO_LABELS.get(sc, "")
    sess_label = f"  Session  : {session_id[:8]}…" if session_id else "  Session  : (none — new chat)"
    print(f"\n  Scenario : [{sc}] {lbl}")
    print(f"  Provider : {prv}  |  {mdl}")
    print(sess_label)
    print(bar())
    print("  [1] Chat              [2] Switch model / scenario")
    print("  [3] My conversations  [4] Config & stats")
    print("  [5] Clear context     [6] Exit")
    print(bar())


# ── Session management menu ─────────────────────────────────────────────────────

def sessions_menu(client: DataStreamClient):
    while True:
        print(f"\n{bar('─')}")
        print("  My Conversations")
        print(bar("─"))

        try:
            sessions = client.list_sessions()
        except Exception as exc:
            print(f"  Error: {exc}")
            return

        if not sessions:
            print("  No saved conversations yet.")
            input("  [Enter] back")
            return

        print(f"  {'#':<4} {'Title':<34} {'Date':<17} {'Msgs':>4}  Scenario")
        print(f"  {'-'*4} {'-'*34} {'-'*17} {'-'*4}  --------")
        for i, s in enumerate(sessions, 1):
            title = (s["title"] or "(untitled)")[:33]
            date  = _fmt_date(s["updated_at"])
            sc    = s["scenario"]
            active = " ◀" if s["id"] == client.session_id else ""
            print(f"  {i:<4} {title:<34} {date:<17} {s['message_count']:>4}  [{sc}]{active}")

        print(f"\n  [R] Resume  [V] View history  [N] Rename  [D] Delete  [B] Back")
        action = input("  Action: ").strip().upper()

        if action == "B":
            return

        if action == "R":
            idx = _pick("Select conversation to resume", [s["title"] or "(untitled)" for s in sessions])
            if idx is not None:
                chosen = sessions[idx]
                client.session_id = chosen["id"]
                # Show last few messages so user knows where they left off
                try:
                    detail = client.get_session(chosen["id"])
                    msgs = detail["messages"][-6:]   # last 3 turns
                    print(f"\n  Resuming: \"{chosen['title']}\"")
                    print(f"  {bar('·')}")
                    if msgs:
                        print("  Last exchanges:")
                        for m in msgs:
                            who = "  You" if m["role"] == "user" else "  Bot"
                            text = m["content"][:120].replace("\n", " ")
                            print(f"  {who}: {text}")
                    else:
                        print("  (no messages yet)")
                    print(f"  {bar('·')}")
                    print(f"  Session active. Select [1] Chat to continue.\n")
                except Exception as exc:
                    print(f"  Could not load history: {exc}")

        elif action == "V":
            idx = _pick("Select conversation to view", [s["title"] or "(untitled)" for s in sessions])
            if idx is not None:
                try:
                    detail = client.get_session(sessions[idx]["id"])
                    print(f"\n  {bar('─')}")
                    print(f"  {detail['title']}  |  {detail['message_count']} messages")
                    print(f"  {bar('─')}")
                    for m in detail["messages"]:
                        who = "You" if m["role"] == "user" else "Bot"
                        print(f"\n  [{who}]  {_fmt_date(m['created_at'])}")
                        for line in m["content"].splitlines():
                            print(f"    {line}")
                    print(f"  {bar('─')}")
                    input("  [Enter] back")
                except Exception as exc:
                    print(f"  Error: {exc}")

        elif action == "N":
            idx = _pick("Select conversation to rename", [s["title"] or "(untitled)" for s in sessions])
            if idx is not None:
                new_title = input("  New title: ").strip()
                if new_title:
                    try:
                        client.rename_session(sessions[idx]["id"], new_title)
                        print("  Title updated.")
                    except Exception as exc:
                        print(f"  Error: {exc}")

        elif action == "D":
            idx = _pick("Select conversation to DELETE", [s["title"] or "(untitled)" for s in sessions])
            if idx is not None:
                sid = sessions[idx]["id"]
                confirm = input(f"  Delete \"{sessions[idx]['title']}\"? (yes/no): ").strip().lower()
                if confirm == "yes":
                    try:
                        client.delete_session(sid)
                        if client.session_id == sid:
                            client.session_id = None
                        print("  Deleted.")
                    except Exception as exc:
                        print(f"  Error: {exc}")


# ── Switch model menu ───────────────────────────────────────────────────────────

def switch_menu(client: DataStreamClient):
    st = client.status()
    print(f"\n{bar('─')}")
    print("  Switch Model / Scenario")
    print(bar("─"))
    print(f"  Current: Scenario {st['active_scenario']}  |  {st['active_provider'].upper()}  |  {st['active_model']}")
    print()

    print("  Scenario:")
    sc_labels = [SCENARIO_LABELS[k] for k in sorted(SCENARIO_LABELS)]
    sc_idx = _pick("Select (Enter to keep)", sc_labels)
    payload: dict = {}
    new_scenario = (sc_idx + 1) if sc_idx is not None else st["active_scenario"]
    if sc_idx is not None:
        payload["scenario"] = new_scenario

    if new_scenario in (1, 2):
        print("\n  Provider:")
        providers = list(PROVIDER_MODELS.keys())
        prov_idx = _pick("Select (Enter to keep)", [p.upper() for p in providers])
        if prov_idx is not None:
            provider = providers[prov_idx]
            payload["provider"] = provider
            print(f"\n  Model for {provider.upper()}:")
            models = PROVIDER_MODELS[provider]
            m_idx = _pick("Select (Enter for default)", models)
            if m_idx is not None:
                payload["model"] = models[m_idx]
    elif new_scenario == 4:
        print("  (Scenario 4 connects directly to Azure Synapse — no LLM provider needed)")

    print("\n  Advanced (Enter to skip):")
    t = input(f"    Temperature [{st.get('temperature', 0.7):.2f}]: ").strip()
    if t:
        try:
            payload["temperature"] = float(t)
        except ValueError:
            pass

    w = input(f"    Memory window 10-20 [{st.get('memory_window_size', 15)}]: ").strip()
    if w.isdigit() and 10 <= int(w) <= 20:
        payload["memory_window_size"] = int(w)

    c = input(f"    Cosine threshold 0-1 [{st.get('cosine_similarity_threshold', 0.7):.2f}]: ").strip()
    if c:
        try:
            val = float(c)
            if 0.0 <= val <= 1.0:
                payload["cosine_similarity_threshold"] = val
        except ValueError:
            pass

    if not payload:
        print("\n  No changes made.")
        return

    result = client.switch(**payload)
    print(f"\n  {result['message']}")
    curr = result["current"]
    print(f"  Scenario  : {curr['scenario']}  |  {curr['provider'].upper()}  |  {curr['model']}")


# ── Chat loop ────────────────────────────────────────────────────────────────────

def _print_meta_tags(meta: dict):
    tags = []
    if meta.get("cached"):
        tags.append("cached")
    if meta.get("rule_matched"):
        tags.append(f"rule:{meta['rule_matched']}")
    if meta.get("retrieved_docs"):
        scores = ", ".join(f"{s:.3f}" for s in (meta.get("cosine_scores") or [])[:3])
        tags.append(f"docs:{meta['retrieved_docs']} [{scores}]")
    if tags:
        print(f"  ⟨{' | '.join(tags)}⟩")


def _print_db_metadata(data: dict):
    """Pretty-print Scenario 4 SQL / row / chart info below the bot reply."""
    m = data.get("metadata") or {}
    if not m:
        return
    intent = m.get("intent", "")
    source = m.get("source", "template")
    row_count = m.get("row_count", 0)
    sql = m.get("sql", "")
    chart = m.get("chart") or {}

    print(f"  ┌─ DB metadata ({source}) ─")
    if intent:
        print(f"  │ Intent    : {intent}")
    print(f"  │ Rows      : {row_count}")
    if sql:
        # Print SQL compactly (first 120 chars)
        sql_preview = sql.replace("\n", " ").strip()
        if len(sql_preview) > 120:
            sql_preview = sql_preview[:117] + "..."
        print(f"  │ SQL       : {sql_preview}")
    if chart:
        path = chart.get("path", "")
        kind = chart.get("chart_type", "")
        title = chart.get("title", "")
        if path:
            label = f"[{kind}]" + (f"  '{title}'" if title else "")
            print(f"  │ Chart     : {path}  {label}")
    print(f"  └{'─' * 50}")


def chat_loop(client: DataStreamClient):
    sess_label = (
        f"  Resuming session {client.session_id[:8]}…"
        if client.session_id else "  Starting new conversation"
    )
    mode = "STREAM" if client.streaming else "BLOCK"
    print(f"\n{bar('─')}")
    print(sess_label + f"   [mode: {mode}]")
    print("  Commands: 'back' menu | 'newsession' fresh | 'stream' toggle")
    print(bar("─"))

    while True:
        try:
            user_input = input("\n  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        cmd = user_input.lower()
        if cmd in ("back", "menu"):
            break
        if cmd == "newsession":
            client.session_id = None
            print("  Session cleared — next message starts a new conversation.")
            continue
        if cmd == "stream":
            client.streaming = not client.streaming
            print(f"  Streaming {'ON' if client.streaming else 'OFF'}")
            continue

        try:
            if client.streaming:
                print("\n  Bot: ", end="", flush=True)
                meta: dict = {}
                for event in client.send_stream(user_input):
                    t = event.get("type")
                    if t == "chunk":
                        print(event.get("content", ""), end="", flush=True)
                    elif t == "meta":
                        meta = event
                    elif t == "error":
                        print(f"\n  Stream error: {event.get('detail')}")
                        break
                print()
                _print_meta_tags(meta)
                _print_db_metadata(meta)
            else:
                r = client.send(user_input)
                print(f"\n  Bot: {r['response']}")
                _print_meta_tags(r)
                _print_db_metadata(r)
        except httpx.HTTPStatusError as exc:
            print(f"\n  HTTP {exc.response.status_code}: {exc.response.text}")
        except Exception as exc:
            print(f"\n  Error: {exc}")


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    print_banner()
    client = DataStreamClient()

    print(f"\n  Connecting to {BASE_URL} as '{USERNAME}' (client_id: terminal) ...")
    if not client.login():
        print("  Cannot authenticate. Check .env and that the server is running.")
        sys.exit(1)
    print("  Authenticated.\n")

    try:
        while True:
            try:
                st = client.status()
            except Exception as exc:
                print(f"  Server unreachable: {exc}")
                break

            print_main_menu(st, client.session_id)
            choice = input("  Select: ").strip()

            if choice == "1":
                chat_loop(client)

            elif choice == "2":
                try:
                    switch_menu(client)
                except Exception as exc:
                    print(f"  Switch failed: {exc}")

            elif choice == "3":
                sessions_menu(client)

            elif choice == "4":
                st = client.status()
                print(f"\n{bar('─')}")
                print("  Configuration & stats")
                print(bar("─"))
                for k, v in st.items():
                    if k not in ("available_scenarios", "available_providers"):
                        print(f"  {k:<38} {v}")
                try:
                    stats = client.memory_stats()
                    print(bar("·"))
                    for k, v in stats.items():
                        print(f"  {k:<38} {v}")
                except Exception:
                    pass

            elif choice == "5":
                if client.session_id:
                    try:
                        client.clear_context()
                        print("  Context window cleared. Next message will have no prior context.")
                        print("  (Full history still saved in DB — resume any time via [3].)")
                    except Exception as exc:
                        print(f"  Error: {exc}")
                else:
                    print("  No active session.")

            elif choice == "6":
                print("\n  Goodbye!\n")
                break

            else:
                print("  Enter 1–6.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
