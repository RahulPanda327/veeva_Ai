"""Parse the JSON object out of an LLM chat-completion response.

OpenAI honours response_format={"type": "json_object"} and returns bare JSON, so
json.loads works directly. Local backends (Ollama, and most OpenAI-compatible
gateways) ignore that parameter and wrap the answer in a markdown fence:

    ```json
    {"title": "..."}
    ```

json.loads rejects that at the leading backtick with the misleading
"Expecting value: line 1 column 1 (char 0)". Some models also add a sentence
before or after the object. This helper tolerates both and is a no-op for
already-clean JSON, so it is safe on every provider.
"""
from __future__ import annotations

import json
import re
from typing import Any, List

# Leading ```/```json and the closing ``` — anchored, so fences inside string
# values are left alone.
_FENCE = re.compile(r"\A\s*```(?:json)?\s*|\s*```\s*\Z", re.IGNORECASE)


def parse_llm_json(content: str | None) -> Any:
    """Return the JSON value in `content`.

    Raises ValueError when there is nothing parseable — callers already treat an
    exception here as "LLM unavailable" and fall back.
    """
    if not content or not content.strip():
        raise ValueError("LLM returned empty content")

    text = _FENCE.sub("", content.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Model wrapped the object in prose — take the outermost {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"LLM returned no parseable JSON: {content[:200]!r}")


_TEXT_KEYS = ("text", "value", "content", "summary", "description", "point", "message")


def as_text(value: Any, default: Any = None) -> Any:
    """Coerce an LLM's idea of "a string" into an actual string.

    Same failure mode as as_str_list but for scalar fields: a model asked for a
    string may answer {"text": "..."} or ["...", "..."], and Pydantic then raises
    on a str-typed field, 500-ing the endpoint. Since these are display strings,
    unwrapping beats failing. `default` is returned for None/empty so callers can
    keep their "no value" contract (usually None) instead of getting "".
    """
    if value is None:
        return default
    if isinstance(value, str):
        return value if value.strip() else default
    if isinstance(value, dict):
        # Prefer a conventional text key, else the first usable string value.
        for key in _TEXT_KEYS:
            if key in value:
                return as_text(value[key], default)
        for nested in value.values():
            got = as_text(nested, None)
            if got:
                return got
        return default
    if isinstance(value, (list, tuple, set)):
        parts = [p for p in (as_text(v, None) for v in value) if p]
        return " ".join(parts) if parts else default
    return str(value)


def as_str_list(value: Any) -> List[str]:
    """Coerce an LLM's idea of "a list of strings" into an actual list of strings.

    A schema field typed List[str] is a promise the model does not always keep —
    smaller/local models return a bare string, a nested list, or a list of
    {"point": "..."} dicts, any of which makes Pydantic raise and turns the whole
    endpoint into a 500. Since the value is display text, normalising is strictly
    better than failing: nested lists are flattened, dicts contribute their first
    string value, everything else is str()'d. Blank entries are dropped.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, (list, tuple, set)):
        return [str(value)]

    out: List[str] = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, (list, tuple, set, dict)):
            out.extend(as_str_list(item))          # flatten one level (recursively)
        else:
            text = str(item).strip()
            if text:
                out.append(text)
    return out
