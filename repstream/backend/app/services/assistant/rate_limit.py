"""Per-device question limit for the AI assistant.

Ten questions per rolling hour, per browser/device, configurable in .env.

IDENTITY
    There is no login, so there is no user id to key on. The identifier is a
    uuid4 minted by this module and stored in an HttpOnly cookie, which is
    per-browser-profile rather than per-network: several people behind one
    office Wi-Fi each get their own quota, which keying on the public IP alone
    would not give (they would share one bucket and lock each other out).

    MAC addresses are not an option: a web server never sees the client's MAC,
    only the MAC of the last router hop.

    The client IP is used as a SECONDARY limit only. A cookie is trivially
    cleared, so without a second axis one person could reset their quota
    indefinitely. The IP ceiling is deliberately looser so a genuinely shared
    network does not trip it in normal use.

ROLLING WINDOW
    Each allowed question appends a timestamp; a request is admitted when the
    number of timestamps newer than (now - window) is under the limit. This is a
    true rolling window rather than a fixed bucket: quota frees up gradually as
    individual questions age out, instead of everyone resetting together on the
    hour and stampeding.

WHAT IS NOT COUNTED
    Blocked requests are not recorded. Counting them would let someone retrying
    in a loop push their own unlock time further away and never be released.
    Empty questions are not counted either - they are a validation failure and
    never reach the model, so charging quota for them would be wrong.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List

from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.utils.cache_paths import cache_file

logger = logging.getLogger(__name__)

_STATE_FILE = cache_file("assistant_rate_limit.json")
_lock = threading.Lock()

# device_id / ip -> list of unix timestamps, newest last
_devices: Dict[str, List[float]] = {}
_ips: Dict[str, List[float]] = {}


def _load() -> None:
    try:
        with open(_STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        _devices.update({k: list(v) for k, v in (data.get("devices") or {}).items()})
        _ips.update({k: list(v) for k, v in (data.get("ips") or {}).items()})
        logger.info("Loaded rate-limit state for %d device(s) from %s",
                    len(_devices), _STATE_FILE.name)
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001 — a corrupt counter file must not stop the app
        logger.warning("Could not load rate-limit state (%s); starting empty.", exc)


def _save() -> None:
    """Persist so counters survive a --reload restart.

    Without this, every code save during development would hand everyone a fresh
    quota, and on the VM an app restart would do the same.
    """
    try:
        tmp = _STATE_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"devices": _devices, "ips": _ips}, f)
        os.replace(tmp, _STATE_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save rate-limit state (%s).", exc)


_load()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _window() -> int:
    return max(1, int(settings.ASSISTANT_RATE_LIMIT_WINDOW_SECONDS))


def _prune(stamps: List[float], now: float) -> List[float]:
    """Drop timestamps that have aged out of the window."""
    cutoff = now - _window()
    return [t for t in stamps if t > cutoff]


def _client_ip(request: Request) -> str:
    """Best available client IP.

    X-Forwarded-For is only consulted when ASSISTANT_TRUST_PROXY_HEADERS is on,
    because any client can send that header: trusting it unconditionally would
    let someone bypass the IP ceiling by making one up per request. Turn it on
    only when the app really does sit behind a proxy that sets it.
    """
    if settings.ASSISTANT_TRUST_PROXY_HEADERS:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _human_delay(seconds: int) -> str:
    """'1 hour' / '43 minutes' / '30 seconds' — the actual wait, not a fixed
    'in 1 hour', so someone 50 minutes in is not told to wait another full hour."""
    seconds = max(1, int(seconds))
    if seconds >= 3600:
        hours = seconds / 3600
        return "1 hour" if round(hours) == 1 else f"{hours:.0f} hours"
    if seconds >= 60:
        mins = round(seconds / 60)
        return "1 minute" if mins == 1 else f"{mins} minutes"
    return f"{seconds} seconds"


@dataclass
class Decision:
    allowed: bool
    device_id: str
    set_cookie: bool = False
    message: str = ""
    retry_after: int = 0          # seconds until the next slot frees up
    remaining: int = 0
    scope: str = ""               # "device" | "ip" — which limit rejected it
    _stamps: List[float] = field(default_factory=list, repr=False)


# ── Public API ───────────────────────────────────────────────────────────────

def resolve_device_id(request: Request) -> tuple[str, bool]:
    """Return (device_id, is_new). Reads the cookie, minting one if absent.

    A malformed value is replaced rather than trusted: the cookie is client-side
    and can be edited by hand, and a caller supplying arbitrary strings could
    otherwise grow the state file without bound.
    """
    raw = request.cookies.get(settings.ASSISTANT_DEVICE_COOKIE_NAME, "")
    try:
        return str(uuid.UUID(raw)), False
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid4()), True


def check(request: Request) -> Decision:
    """Decide whether this request may ask a question. Records nothing."""
    device_id, is_new = resolve_device_id(request)

    if not settings.ASSISTANT_RATE_LIMIT_ENABLED:
        return Decision(allowed=True, device_id=device_id, set_cookie=is_new,
                        remaining=int(settings.ASSISTANT_RATE_LIMIT_QUESTIONS))

    now = time.time()
    limit = max(1, int(settings.ASSISTANT_RATE_LIMIT_QUESTIONS))
    ip_limit = max(limit, int(settings.ASSISTANT_RATE_LIMIT_IP_QUESTIONS))
    ip = _client_ip(request)

    with _lock:
        stamps = _prune(_devices.get(device_id, []), now)
        _devices[device_id] = stamps
        ip_stamps = _prune(_ips.get(ip, []), now)
        _ips[ip] = ip_stamps

    if len(stamps) >= limit:
        # Oldest question in the window decides when a slot frees up.
        retry = int(stamps[0] + _window() - now) + 1
        return Decision(
            allowed=False, device_id=device_id, set_cookie=is_new, scope="device",
            retry_after=retry, remaining=0,
            # The count is deliberately left out: the user cannot act on it, and
            # naming the exact quota tells anyone probing the endpoint precisely
            # what it is. The wait is the only part they need.
            message=f"You've reached your limit. You can ask again in {_human_delay(retry)}.",
        )

    if len(ip_stamps) >= ip_limit:
        retry = int(ip_stamps[0] + _window() - now) + 1
        return Decision(
            allowed=False, device_id=device_id, set_cookie=is_new, scope="ip",
            retry_after=retry, remaining=0,
            message=(f"This network has reached its shared limit. "
                     f"You can ask again in {_human_delay(retry)}."),
        )

    return Decision(allowed=True, device_id=device_id, set_cookie=is_new,
                    remaining=limit - len(stamps), _stamps=stamps)


def record(request: Request, decision: Decision) -> None:
    """Count one answered question against the device and its IP."""
    if not settings.ASSISTANT_RATE_LIMIT_ENABLED:
        return
    now = time.time()
    ip = _client_ip(request)
    with _lock:
        _devices.setdefault(decision.device_id, []).append(now)
        _ips.setdefault(ip, []).append(now)
        # Drop devices and IPs with nothing left in the window, so the file
        # tracks current users instead of growing once per cookie ever issued.
        for bucket in (_devices, _ips):
            for key in [k for k, v in bucket.items() if not _prune(v, now)]:
                del bucket[key]
        _save()


def apply_cookie(response: Response, decision: Decision) -> None:
    """Set the device cookie when this request minted a new one.

    HttpOnly so page scripts cannot read or forge it. SameSite=Lax is the safe
    default; a UI served from a different site needs SameSite=None with
    Secure=true, which requires HTTPS.
    """
    if not decision.set_cookie:
        return
    response.set_cookie(
        key=settings.ASSISTANT_DEVICE_COOKIE_NAME,
        value=decision.device_id,
        max_age=int(settings.ASSISTANT_COOKIE_MAX_AGE_DAYS) * 24 * 3600,
        httponly=True,
        secure=bool(settings.ASSISTANT_COOKIE_SECURE),
        samesite=settings.ASSISTANT_COOKIE_SAMESITE or "lax",
        path="/",
    )
