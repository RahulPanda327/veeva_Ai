"""
Embed everything in kb/ into the vector store.

kb/ IS THE INPUT LIST
    Every file in kb/ (including sub-folders) is discovered and embedded. There
    is no list of filenames to maintain here: drop a file in, re-run, it is
    indexed; delete one, re-run, its rows are removed. Adding a document used to
    mean editing this script too, and the two drifted - three markdown docs were
    listed here long after they had been replaced on disk, so the replacement
    sat in kb/ unembedded while the script reported the old names as "not found"
    every run.

    The store's own files live in ../embeddings/, NOT in kb/, precisely so this
    scan cannot pick up its own output and embed it.

HOW A FILE IS CHUNKED  (by extension - see _chunk_file)
    .md .markdown   split on '## ' headings, H1 title carried into every chunk
    .txt            split on '=====' dividers; falls back to header-detection
                    for files that use neither
    .json           greetings (objects with triggers/responses) or Q&A entries,
                    detected from the content rather than the filename

    A file with any other extension is skipped and reported as such, so an
    unexpected .pdf or .xlsx in kb/ is visible in the summary instead of
    silently contributing nothing.

Run it any time the KB changes:

    cd ai_assistant
    python -m scripts.ingest_to_pgvector

Or with a direct path:
    python ai_assistant/scripts/ingest_to_pgvector.py

Set INGEST_VERBOSE=1 for a line per chunk instead of a line per file.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sys
from pathlib import Path

# Allow running as a script from any working directory
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db_qa.vector_store import get_vector_store, store_label  # noqa: E402

KB_DIR = ROOT / "kb"

# Extensions this script knows how to turn into chunks. Anything else found in
# kb/ is listed in the summary as skipped rather than passed over in silence -
# a .docx dropped in by mistake should be visible, not invisible.
_SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".json"}

# Never treated as input, even if an old copy is still sitting in kb/: these are
# the store's own output (it now writes to ../embeddings/), and editor/OS litter.
_IGNORED_NAMES = {"embeddings.npz", "embeddings_meta.json", ".ds_store", "thumbs.db"}
_IGNORED_SUFFIXES = {".tmp", ".bak", ".swp"}

# Sources that predate filename-derived naming. Cleared on every run so their
# rows cannot outlive the files they came from. Only needed for backends that
# cannot enumerate their own sources (pgvector); the local store reports them
# via sources() and stale rows are dropped automatically.
_RETIRED_SOURCES = ("context_file", "kb_question", "business_logic",
                    "system_instructions", "module_knowledge", "data_quality")

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


def chunk_markdown_file(path: Path, source: str) -> list[dict]:
    """Split a markdown doc on its `## ` headings.

    Every chunk keeps the document's `# ` title prefixed to it. Retrieval returns
    one chunk with no surrounding context, so a section headed "## 3. Access
    scope" is ambiguous on its own - scope of WHAT? Carrying the H1 down into each
    chunk is what lets the model tell these three documents apart, and it is the
    same lesson as the live-data export: a heading that lives in a different chunk
    from its body might as well not exist.

    Sections longer than _MAX_CHUNK_CHARS are split rather than truncated.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    doc_title = ""
    for line in lines[:10]:
        if line.startswith("# "):
            doc_title = line.lstrip("# ").strip()
            break
    doc_title = doc_title or path.stem

    # Walk the file accumulating lines under the current H2.
    sections: list[tuple[str, list[str]]] = []
    current_head, current_body = doc_title, []
    for line in lines:
        if line.startswith("## "):
            if any(l.strip() for l in current_body):
                sections.append((current_head, current_body))
            current_head, current_body = line.lstrip("# ").strip(), []
        else:
            current_body.append(line)
    if any(l.strip() for l in current_body):
        sections.append((current_head, current_body))

    chunks: list[dict] = []
    for i, (head, body) in enumerate(sections, 1):
        body_text = "\n".join(body).strip()
        if len(body_text) < 40:
            continue                       # a heading with nothing under it
        title = f"{doc_title} — {head}" if head != doc_title else doc_title
        for j, piece in enumerate(_split_long(body_text, _MAX_CHUNK_CHARS), 1):
            suffix = f"_p{j}" if j > 1 else ""
            chunks.append({
                "chunk_id": f"{source}_{i}{suffix}",
                "title": title,
                # Title repeated inside the content so it is embedded too, not
                # just stored as metadata the vector never sees.
                "content": f"{title}\n\n{piece}",
            })
    return chunks


def load_greetings(data) -> list[dict]:
    """One chunk per greeting rule.

    NOTE: chat_svc answers greetings by exact trigger match BEFORE searching, so
    these embeddings are not what makes "hi" work - that path is unchanged. They
    only help when a greeting is phrased conversationally enough to miss the
    exact match ("hey there, good morning"). The trade is a little retrieval
    noise: a short vague question can now match a greeting chunk instead of real
    data. If that shows up, drop this source rather than lowering top_k.

    Takes already-parsed JSON rather than a path: the caller has to read and
    decode the file anyway to work out whether it holds greetings or Q&A pairs,
    and parsing the same file twice invites the two reads to disagree.
    """
    rules = data if isinstance(data, list) else []
    chunks: list[dict] = []
    for i, rule in enumerate(rules, 1):
        triggers = [str(t) for t in (rule.get("triggers") or []) if t]
        responses = [str(r) for r in (rule.get("responses") or []) if r]
        if not triggers or not responses:
            continue
        chunks.append({
            "chunk_id": f"greeting_{i}",
            "title": f"Greeting: {triggers[0]}",
            "content": ("Conversational greeting or small talk.\n"
                        f"User says: {', '.join(triggers)}\n"
                        f"Assistant replies: {responses[0]}"),
        })
    return chunks


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


def load_kb_questions(data) -> list[dict]:
    """
    Load every Q&A entry from a KB questions JSON file.
    Combines title + question + description + module into a single content string
    for richer embedding coverage.
    Returns a list of dicts with keys: chunk_id, title, content, metadata.
    """
    # Unwrap envelope: {"query details": [...]} → [...]
    if isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list):
                data = val
                break
    if not isinstance(data, list):
        return []

    items: list[dict] = []
    for q in data:
        if not isinstance(q, dict):
            continue                      # a bare string or number in the list
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


# ── Discovery ─────────────────────────────────────────────────────────────────────

def discover_kb_files() -> list[Path]:
    """Every candidate input file in kb/, sorted, sub-folders included.

    Sorted so the row order in the store is reproducible across runs and across
    machines - iteration order off the filesystem is not, and an unstable order
    makes two ingests of identical content produce diffs that look like real
    changes.
    """
    if not KB_DIR.is_dir():
        return []
    files = [
        p for p in KB_DIR.rglob("*")
        if p.is_file()
        and not p.name.startswith(".")
        and p.name.lower() not in _IGNORED_NAMES
        and p.suffix.lower() not in _IGNORED_SUFFIXES
    ]
    return sorted(files, key=lambda p: str(p.relative_to(KB_DIR)).lower())


def source_name(path: Path) -> str:
    """Stable source id derived from the file's path relative to kb/.

    The path, not just the stem, so kb/a/notes.md and kb/b/notes.md stay
    distinct instead of silently clearing each other's rows mid-run.
    """
    rel = path.relative_to(KB_DIR).with_suffix("")
    slug = re.sub(r"[^a-z0-9]+", "_", str(rel).lower()).strip("_")
    return slug or "kb_file"


def _looks_like_greetings(data) -> bool:
    """Greeting rules are a list of objects carrying triggers and responses.

    Detected from the content rather than the filename so a renamed file keeps
    being chunked the right way - the shape is what actually determines which
    loader can read it.
    """
    if not isinstance(data, list):
        return False
    return any(isinstance(r, dict) and "triggers" in r and "responses" in r
               for r in data[:5])


def _chunk_file(path: Path, source: str) -> tuple[list[dict], str]:
    """Chunk one KB file. Returns (chunks, status).

    status is "embedded" when the file was understood, or a short reason when it
    was not - which is what lands in the summary table.
    """
    suffix = path.suffix.lower()

    if suffix in (".md", ".markdown"):
        return chunk_markdown_file(path, source), "embedded"

    if suffix == ".txt":
        text = path.read_text(encoding="utf-8")
        # '=====' dividers are the live-export format. A .txt without them is
        # more likely prose with plain title lines, which the header-based
        # chunker handles far better than one 2000-char slice at a time.
        chunks = (chunk_context_file(path) if _DIVIDER.search(text)
                  else chunk_business_logic_file(path))
        return chunks, "embedded"

    if suffix == ".json":
        text = path.read_text(encoding="utf-8").strip()
        try:
            # raw_decode stops at the first valid JSON value — handles files with
            # extra content appended after the main object.
            data, _ = json.JSONDecoder().raw_decode(text)
        except ValueError as exc:
            return [], f"invalid JSON ({exc.args[0][:40]})"
        if _looks_like_greetings(data):
            return load_greetings(data), "embedded"
        return load_kb_questions(data), "embedded"

    return [], f"unsupported {suffix or 'file'}"


def _prefixed(chunk_id: str, source: str) -> str:
    """Namespace a chunk id under its source.

    The per-format chunkers number from 1 within their own file, so without this
    two files would both produce 'context_section_1' and the ids would no longer
    identify anything. Ids that already lead with the source are left alone.
    """
    cid = str(chunk_id or "").strip()
    if not cid:
        return source
    return cid if cid.startswith(source) else f"{source}__{cid}"


# ── Main ──────────────────────────────────────────────────────────────────────────

# Per-file outcome, printed as a summary block at the very end.
#   (filename, source, chunks, status)
_SUMMARY: list[tuple[str, str, int, str]] = []

# Per-chunk lines are useful when debugging a single file and pure noise
# otherwise: 138 of them bury everything else. Off unless INGEST_VERBOSE is set.
_VERBOSE = os.getenv("INGEST_VERBOSE", "").strip().lower() in ("1", "true", "yes", "on")


def _done(path_name: str, source: str, count: int, status: str = "embedded") -> None:
    """Record one file's outcome and print its completion line as it happens."""
    _SUMMARY.append((path_name, source, count, status))
    mark = "OK  " if status == "embedded" else "SKIP"
    print(f"  [{mark}] {path_name} -> {source}: {count} chunk(s) {status}")


def _print_summary(store) -> None:
    """Compact per-file table, printed LAST.

    warm_cache.py logs only the final 12 lines of this script's output, so a
    summary anywhere else scrolls away and the run looks like it only touched
    whichever file happened to be ingested last. Keeping this short enough to
    survive that tail is the whole point.
    """
    print("\n" + "=" * 62)
    print("EMBEDDING SUMMARY")
    for name, source, count, status in _SUMMARY:
        mark = "OK  " if status == "embedded" else "SKIP"
        print(f"  [{mark}] {name:<44} {count:>4}")
    embedded = [s for s in _SUMMARY if s[3] == "embedded"]
    print(f"  {len(embedded)} file(s) embedded, {len(_SUMMARY) - len(embedded)} skipped "
          f"-> {store.count()} rows total")
    print("=" * 62)


def main() -> None:
    store = get_vector_store()

    # This runs as its own process (spawned by warm_cache.py), so it cannot rely
    # on the server's startup banner - and this is the one place where the
    # embedding model choice actually decides what ends up on disk.
    from db_qa.embedder import get_embedder   # noqa: PLC0415

    emb = get_embedder()
    print("=" * 62)
    print(f"EMBEDDING MODEL : {emb.backend.upper()} / {emb.model} ({emb.dim}-dim)")
    print(f"VECTOR STORE    : {store_label()}")
    print("=" * 62)
    store.ensure_table()

    # The local store persists on every store() unless told otherwise. Batching
    # the whole ingest into one write is both faster and far less likely to
    # collide with another process holding the file. pgvector has no such
    # method, so fall back to a no-op context for it.
    bulk = getattr(store, "bulk", None)
    with bulk() if bulk else contextlib.nullcontext():
        _ingest_all(store)
    # Printed AFTER the context exits, i.e. after the single write has actually
    # landed. Reporting success before the flush is how a failed write ends up
    # looking like a completed ingest.
    _print_summary(store)


def _ingest_all(store) -> int:
    """Embed every file kb/ currently holds, then drop anything it no longer does."""
    files = discover_kb_files()
    if not files:
        print(f"  WARNING: no files found in {KB_DIR}")
        return store.count()

    print(f"Found {len(files)} file(s) in {KB_DIR.name}/")

    seen: set[str] = set()
    for path in files:
        rel = str(path.relative_to(KB_DIR))
        source = source_name(path)
        seen.add(source)
        print(f"\nReading {rel} ...")

        try:
            chunks, status = _chunk_file(path, source)
        except Exception as exc:  # noqa: BLE001
            # One unreadable file must not abandon the other twenty. It is
            # reported in the summary and its old rows are left untouched, which
            # is better than clearing them and ending up with neither.
            print(f"  ERROR: {exc}")
            _done(rel, source, 0, f"failed ({type(exc).__name__})")
            continue

        if status != "embedded":
            print(f"  SKIP: {status}")
            _done(rel, source, 0, status)
            continue

        # Cleared only once the file has parsed, so a chunker raising halfway
        # cannot leave the source with nothing in it.
        store.clear_source(source)
        for i, chunk in enumerate(chunks, 1):
            store.store(
                source=source,
                chunk_id=_prefixed(chunk["chunk_id"], source),
                title=chunk["title"],
                content=chunk["content"],
                # Every row records the file it came from, so a wrong answer can
                # be traced back to a document rather than just a source slug.
                metadata={**chunk.get("metadata", {}), "file": rel},
            )
            if _VERBOSE:
                print(f"    [{i}/{len(chunks)}] {chunk['chunk_id']} — {chunk['title'][:65]}")
        _done(rel, source, len(chunks))

    _clear_stale(store, seen)
    return store.count()


def _clear_stale(store, seen: set[str]) -> None:
    """Drop rows for sources that no longer have a file in kb/.

    Deleting a KB file used to leave its embeddings behind for good - a source
    was only ever cleared inside the branch that re-read its file, so a file that
    was gone had no branch to run. The assistant went on answering from documents
    that no longer existed.

    Backends that can enumerate their own sources (the local store) get this
    exactly. pgvector cannot, so it falls back to the hardcoded list of names
    known to have been retired.
    """
    lister = getattr(store, "sources", None)
    if lister is None:
        for source in _RETIRED_SOURCES:
            store.clear_source(source)
        return

    stale = sorted(set(lister()) - seen)
    for source in stale:
        store.clear_source(source)
    if stale:
        print(f"\nRemoved {len(stale)} source(s) with no file in kb/: {', '.join(stale)}")


if __name__ == "__main__":
    main()
