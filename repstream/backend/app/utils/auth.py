"""Caller identity for the API.

AUTHENTICATION IS DISABLED. Every request resolves to the single identity below
without presenting any credential, and no request can be rejected with 401.

Why it is not simply deleted: the routers scope all their data by
`rep.territory_id`, so they still need an identity object. What was removed is
the credential CHECK, not the identity.

The JWT helpers below are kept because tests and scripts/generate_test_token.py
import them, and because restoring real auth means putting the check back into
get_current_rep - see the note there.

Do not deploy this to production or anywhere reachable by untrusted users: the
whole API is open, and every caller sees the same rep's data.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


class RepIdentity(BaseModel):
    rep_id: str
    territory_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "rep"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> RepIdentity:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        rep_id: str = payload.get("sub", "")
        territory_id: str = payload.get("territory_id", "")
        if not rep_id or not territory_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return RepIdentity(
            rep_id=rep_id,
            territory_id=territory_id,
            email=payload.get("email"),
            full_name=payload.get("full_name"),
            role=payload.get("role", "rep"),
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials") from exc


_DEV_IDENTITY = RepIdentity(
    rep_id="REP001",
    territory_id="Commercial_Sales_Field_Force|A0E000000013008",  # real territory ID verified against live Synapse
    email="rahulpandarp1998@gmail.com",
    full_name="Demo Rep",
    role="rep",
)


def get_current_rep() -> RepIdentity:
    """The caller's identity. Always the same one — nothing is verified.

    No Authorization header is read, so no request can 401. The DEV_SKIP_AUTH
    setting is no longer consulted; it is left in config.py only so an existing
    .env carrying it does not fail to load.

    TO RESTORE REAL AUTHENTICATION, put back the check this replaced:

        def get_current_rep(
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
        ) -> RepIdentity:
            if settings.DEV_SKIP_AUTH:
                return _DEV_IDENTITY
            if credentials is None:
                raise HTTPException(status_code=401, detail="Not authenticated")
            return decode_token(credentials.credentials)

    and restore the token-based branch in response_cache.caller_key(), which was
    flattened to a single shared namespace to match.
    """
    return _DEV_IDENTITY
