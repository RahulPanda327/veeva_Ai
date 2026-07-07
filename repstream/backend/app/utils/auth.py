"""JWT authentication utilities and FastAPI dependency."""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

_DEV_SKIP_AUTH = settings.DEV_SKIP_AUTH


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


def get_current_rep(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> RepIdentity:
    # DEV_SKIP_AUTH=true bypasses JWT — never use in production
    if _DEV_SKIP_AUTH:
        return _DEV_IDENTITY
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_token(credentials.credentials)
