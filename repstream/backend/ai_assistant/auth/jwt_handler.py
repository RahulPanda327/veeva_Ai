"""
JWT token structure
───────────────────
Payload fields:
  sub         — username (subject)
  jti         — unique token ID (for future revocation support)
  client_id   — which client issued the login: web | mobile | terminal | api
  token_type  — always "access"
  iat         — issued-at timestamp
  exp         — expiry timestamp

TokenData (decoded) is injected into every protected route via get_current_user().
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel

from config.settings import get_config


class TokenData(BaseModel):
    """Decoded claims extracted from a verified JWT."""
    username: str
    jti: str = ""
    client_id: str = "api"
    exp: Optional[datetime] = None


class TokenResponse(BaseModel):
    """Returned to the caller after successful login."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int        # seconds
    client_id: str


def create_token(username: str, client_id: str = "api") -> TokenResponse:
    cfg = get_config()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=cfg.jwt_expiry_hours)
    token_id = str(uuid.uuid4())

    payload = {
        "sub": username,
        "jti": token_id,
        "client_id": client_id,
        "token_type": "access",
        "iat": now,
        "exp": expire,
    }
    token = jwt.encode(payload, cfg.jwt_secret_key, algorithm=cfg.jwt_algorithm)
    return TokenResponse(
        access_token=token,
        expires_in=cfg.jwt_expiry_hours * 3600,
        client_id=client_id,
    )


def verify_token(token: str) -> TokenData:
    cfg = get_config()
    try:
        payload = jwt.decode(
            token,
            cfg.jwt_secret_key,
            algorithms=[cfg.jwt_algorithm],
        )
        username: Optional[str] = payload.get("sub")
        if not username:
            raise ValueError("Token missing subject claim")
        return TokenData(
            username=username,
            jti=payload.get("jti", ""),
            client_id=payload.get("client_id", "api"),
        )
    except JWTError as exc:
        raise ValueError(f"Token validation failed: {exc}") from exc
