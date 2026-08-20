"""
Ingest knowledge base content into pgvector for scenario_2 semantic fallback.

Three sources are ingested:
  1. kb/CONTEXT_file.txt                   — chunked by === section dividers
                                             (source = 'context_file')
  2. kb/kb_chatbot_questions_updated.json  — one row per question
                                             (source = 'kb_question')
  3. kb/business_logic.txt                 — chunked by section headers
                                             (source = 'business_logic')

Run once to populate, then re-run any time the KB files change:

    cd Datastream-Chatbot
    python -m scripts.ingest_to_pgvector

Or with a direct path:
    python Datastream-Chatbot/scripts/ingest_to_pgvector.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Allow running as a script from any working directory
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db_qa.pgvector_store import get_pgvector_store, TABLE_NAME  # noqa: E402

KB_DIR              = ROOT / "kb"
CONTEXT_FILE        = KB_DIR / "updated_context_file.txt"
QUESTIONS_FILE      = KB_DIR / "kb_chatbot_questions_updated.json"
BUSINESS_LOGIC_FILE = KB_DIR / "business_logic.txt"
# Written by the RepStream warm-up — the live application data (HCP priorities,
# alerts, objections, new writers). Uses the same === dividers as the context file.
REPSTREAM_LIVE_FILE = KB_DIR / "repstream_live_data.txt"

# Lines that are nothing but '=' characters (section dividers)
_DIVIDER = re.compile(r"^={10,}\s*$", re.MULTILINE)

# Maximum characters per context chunk (keeps embeddings focused)
_MAX_CHUNK_CHARS = 2000


# ── Chunkers ─────────────────────────────────────────────────────────────────────

# Lines that introduce a section (title, territory scope). Repeated on every piece
# a long section is split into, so each piece still says what it is about.
_HEADER_MAX_LINES = 4


def _section_header(lines: list[str]) -> str:
    """The opening lines of a section, up to the first blank line.

    For the live-data sections this is the title plus the 'Territory scope:'
    lines. Carrying it onto every piece is what stops piece 7 of a territory's
    HCP list from being an anonymous list of names with no territory attached.
    """
    header: list[str] = []
    for line in lines[:_HEADER_MAX_LINES]:
        if not line.strip():
            break
        header.append(line)
    return "\n".join(header)


def _split_long(part: str, max_chars: int) -> list[str]:
    """Split an over-long section into pieces of <= max_chars, on line boundaries.

    Previously this content was simply cut at max_chars, which silently dropped
    82% of the live-data file — a territory section listing 40 HCPs kept only the
    first handful, so questions about anyone further down could never be answered.
    Splitting keeps every line; the section header is repeated on each piece so
    the scope survives.
    """
    if len(part) <= max_chars:
        return [part]

    lines = part.splitlines()
    header = _section_header(lines)
    body = lines[len(header.splitlines()):] if header else lines

    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    budget = max_chars - len(header) - 2      # room to re-add the header

    for line in body:
        # A single line longer than the budget still has to go somewhere; give it
        # its own piece rather than dropping it.
        if current and current_len + len(line) + 1 > budget:
            pieces.append(f"{header}\n" + "\n".join(current) if header else "\n".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += len(line) + 1

    if current:
        pieces.append(f"{header}\n" + "\n".join(current) if header else "\n".join(current))

    return [p.strip() for p in pieces if p.strip()]


def chunk_context_file(path: Path) -> list[dict]:
    """
    Split CONTEXT_file.txt into logical sections using the === dividers, then
    split any section that exceeds _MAX_CHUNK_CHARS into several chunks so that
    nothing is discarded.
    Returns a list of dicts with keys: chunk_id, title, content.
    """
    text = path.read_text(encoding="utf-8")
    parts = _DIVIDER.split(text)

    chunks: list[dict] = []
    section_num = 0

    for part in parts:
        part = part.strip()
        if len(part) < 80:
            continue  # skip tiny fragments (raw divider text, blank gaps)

        # Try to pull a meaningful title from the first few lines
        lines = part.splitlines()
        title = ""
        for line in lines[:6]:
            stripped = line.strip()
            if stripped and (
                stripped.startswith("SECTION")
                or "MODULE" in stripped
                or "MODULE_NAME" in stripped
            ):
                title = stripped
                break
        if not title and lines:
            title = lines[0].strip()

        section_num += 1
        pieces = _split_long(part, _MAX_CHUNK_CHARS)
        for piece_num, piece in enumerate(pieces, 1):
            # Single-piece sections keep their original id so existing ids are
            # unchanged; only split sections gain a _pN suffix.
            suffix = "" if len(pieces) == 1 else f"_p{piece_num}"
            part_label = "" if len(pieces) == 1 else f" (part {piece_num} of {len(pieces)})"
            chunks.append({
                "chunk_id": f"context_section_{section_num}{suffix}",
                "title":    (title + part_label)[:200],
                "content":  piece,
            })

    return chunks


def load_kb_questions(path: Path) -> list[dict]:
    """
    Load every entry from kb_chatbot_questions_updated.json.
    Combines title + question + description + module into a single content string
    for richer embedding coverage.
    Returns a list of dicts with keys: chunk_id, title, content, metadata.
    """
    text = path.read_text(encoding="utf-8").strip()
    # raw_decode stops at the first valid JSON object — handles files with
    # extra content appended after the main object (e.g. Module_Details block)
    data, _ = json.JSONDecoder().raw_decode(text)

    # Unwrap envelope: {"query details": [...]} → [...]
    if isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list):
                data = val
                break

    items: list[dict] = []
    for q in data:
        qvar        = q.get("Query_variable", "")
        title       = q.get("title", "")
        question    = q.get("questions", "")
        description = q.get("description", "")
        module      = q.get("module", "")

        parts: list[str] = []
        if title:
            parts.append(f"Title: {title}")
        if question:
            parts.append(f"Question: {question}")
        if description:
            parts.append(f"Description: {description}")
        if module:
            parts.append(f"Module: {module}")
        content = ". ".join(parts)

        items.append({
            "chunk_id": qvar,
            "title":    title,
            "content":  content,
            "metadata": {
                "query_variable": qvar,
                "question":       question,
                "description":    description,
                "module":         module,
            },
        })

    return items


def chunk_business_logic_file(path: Path) -> list[dict]:
    """
    Split business_logic.txt into chunks by section headers.
    A section header is a non-empty line that does NOT start with
    '-', a digit, or whitespace (i.e. it's a plain title line).
    """
    lines = path.read_text(encoding="utf-8").splitlines()

    chunks: list[dict] = []
    current_title   = "Business Logic"
    current_lines:  list[str] = []
    section_num     = 0

    def _flush():
        nonlocal section_num
        content = "\n".join(current_lines).strip()
        if len(content) < 30:
            return
        section_num += 1
        chunks.append({
            "chunk_id": f"business_logic_section_{section_num}",
            "title":    current_title[:200],
            "content":  content[:_MAX_CHUNK_CHARS],
        })

    for line in lines:
        stripped = line.strip()
        # Detect a section header: non-empty, doesn't start with -, digit, or space
        is_header = (
            stripped
            and not stripped.startswith("-")
            and not stripped[0].isdigit()
            and not line.startswith(" ")
            and not line.startswith("\t")
        )
        if is_header and current_lines:
            _flush()
            current_title = stripped
            current_lines = [stripped]
        else:
            current_lines.append(line)

    _flush()  # flush the last section
    return chunks


# ── Main ──────────────────────────────────────────────────────────────────────────

def main() -> None:
    store = get_pgvector_store()

    print(f"Setting up table '{TABLE_NAME}' and HNSW index ...")
    store.ensure_table()

    # ── Context file ─────────────────────────────────────────────────────────────
    print(f"\nReading {CONTEXT_FILE.name} ...")
    if not CONTEXT_FILE.exists():
        print(f"  WARNING: {CONTEXT_FILE} not found — skipping context file ingestion")
    else:
        context_chunks = chunk_context_file(CONTEXT_FILE)
        print(f"  {len(context_chunks)} sections extracted")
        print("  Clearing old 'context_file' rows ...")
        store.clear_source("context_file")
        for i, chunk in enumerate(context_chunks, 1):
            store.store(
                source="context_file",
                chunk_id=chunk["chunk_id"],
                title=chunk["title"],
                content=chunk["content"],
            )
            print(
                f"  [{i:02d}/{len(context_chunks):02d}] "
                f"{chunk['chunk_id']} — {chunk['title'][:65]}"
            )

    # ── KB questions ─────────────────────────────────────────────────────────────
    print(f"\nReading {QUESTIONS_FILE.name} ...")
    if not QUESTIONS_FILE.exists():
        print(f"  WARNING: {QUESTIONS_FILE} not found — skipping KB question ingestion")
    else:
        kb_items = load_kb_questions(QUESTIONS_FILE)
        print(f"  {len(kb_items)} questions loaded")
        print("  Clearing old 'kb_question' rows ...")
        store.clear_source("kb_question")
        for i, item in enumerate(kb_items, 1):
            store.store(
                source="kb_question",
                chunk_id=item["chunk_id"],
                title=item["title"],
                content=item["content"],
                metadata=item["metadata"],
            )
            print(
                f"  [{i:02d}/{len(kb_items):02d}] "
                f"{item['chunk_id']} — {item['title']}"
            )

    # ── Business logic file ───────────────────────────────────────────────────────
    print(f"\nReading {BUSINESS_LOGIC_FILE.name} ...")
    if not BUSINESS_LOGIC_FILE.exists():
        print(f"  WARNING: {BUSINESS_LOGIC_FILE} not found — skipping business logic ingestion")
    else:
        bl_chunks = chunk_business_logic_file(BUSINESS_LOGIC_FILE)
        print(f"  {len(bl_chunks)} sections extracted")
        print("  Clearing old 'business_logic' rows ...")
        store.clear_source("business_logic")
        for i, chunk in enumerate(bl_chunks, 1):
            store.store(
                source="business_logic",
                chunk_id=chunk["chunk_id"],
                title=chunk["title"],
                content=chunk["content"],
            )
            print(
                f"  [{i:02d}/{len(bl_chunks):02d}] "
                f"{chunk['chunk_id']} — {chunk['title'][:65]}"
            )

    # ── RepStream live data ───────────────────────────────────────────────────────
    # Regenerated by the RepStream warm-up (scripts/export_live_to_kb.py), so this
    # is the only source whose content changes between runs. Cleared and re-stored
    # each time rather than merged: stale HCP counts and alert dates would
    # otherwise sit alongside current ones and the retriever could return either.
    print(f"\nReading {REPSTREAM_LIVE_FILE.name} ...")
    if not REPSTREAM_LIVE_FILE.exists():
        print(f"  WARNING: {REPSTREAM_LIVE_FILE} not found — skipping live data ingestion")
        print("  Run 'python scripts/export_live_to_kb.py' in the RepStream backend first.")
    else:
        live_chunks = chunk_context_file(REPSTREAM_LIVE_FILE)   # same === divider format
        print(f"  {len(live_chunks)} sections extracted")
        print("  Clearing old 'repstream_live' rows ...")
        store.clear_source("repstream_live")
        for i, chunk in enumerate(live_chunks, 1):
            store.store(
                source="repstream_live",
                chunk_id=chunk["chunk_id"].replace("context_section", "repstream_live"),
                title=chunk["title"],
                content=chunk["content"],
            )
            print(
                f"  [{i:02d}/{len(live_chunks):02d}] "
                f"{chunk['chunk_id']} — {chunk['title'][:65]}"
            )

    total = store.count()
    print(f"\nIngestion complete. Total rows in '{TABLE_NAME}': {total}")


if __name__ == "__main__":
    main()
