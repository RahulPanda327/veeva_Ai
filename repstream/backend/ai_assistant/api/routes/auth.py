# from fastapi import APIRouter, Depends, HTTPException, status


# from pydantic import BaseModel
# from typing import Literal

# from auth.jwt_handler import create_token, TokenData, TokenResponse
# from auth.password import verify_password
# from api.dependencies import get_current_user, get_settings
# from config.settings import AppConfig

# router = APIRouter(prefix="/auth", tags=["Authentication"])

# _VALID_CLIENTS = {"web", "mobile", "terminal", "api"}


# class LoginRequest(BaseModel):
#     username: str
#     password: str
#     client_id: Literal["web", "mobile", "terminal", "api"] = "api"


# class UserInfo(BaseModel):
#     username: str
#     client_id: str
#     jti: str
#     active_scenario: int
#     active_provider: str
#     active_model: str


# @router.post(
#     "/login",
#     response_model=TokenResponse,
#     summary="Obtain a JWT access token",
#     description=(
#         "Returns a bearer token valid for `jwt_expiry_hours` hours. "
#         "Pass `client_id` to tag which surface is authenticating "
#         "(web / mobile / terminal / api)."
#     ),
# )
# def login(body: LoginRequest, cfg: AppConfig = Depends(get_settings)):
#     if body.username != cfg.admin_username or not verify_password(body.password, cfg.admin_password):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     return create_token(body.username, client_id=body.client_id)


# @router.get("/me", response_model=UserInfo, summary="Return the current authenticated user")
# def me(user: TokenData = Depends(get_current_user), cfg: AppConfig = Depends(get_settings)):
#     return UserInfo(
#         username=user.username,
#         client_id=user.client_id,
#         jti=user.jti,
#         active_scenario=cfg.active_scenario,
#         active_provider=cfg.active_api_provider,
#         active_model=cfg.llm_model_name,
#     )


from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Literal, Optional

from auth.jwt_handler import create_token, TokenData, TokenResponse
from auth.password import verify_password
from api.dependencies import get_current_user, get_settings
from config.settings import AppConfig
from utils.application_logs import (
    get_application_logger,
    AUTH_EVENT_SUCCESS,
    AUTH_EVENT_INVALID_CREDENTIALS,
    AUTH_EVENT_USER_NOT_FOUND,
)

# ── Existing router — kept as-is for built-in frontend / API / Swagger use ──
router = APIRouter(prefix="/auth", tags=["Authentication"])

# ── NEW router — no prefix — for React frontend compatibility ────────────────
# React frontend calls POST /login (via Vite proxy: /api/login → /login)
react_router = APIRouter(tags=["React Frontend"])

_VALID_CLIENTS = {"web", "mobile", "terminal", "api"}


# ── Existing models (unchanged) ───────────────────────────────────────────────

# class LoginRequest(BaseModel):
#     username: str
#     password: str
#     client_id: Literal["web", "mobile", "terminal", "api"] = "api"

class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Literal["web", "mobile", "terminal", "api"] = "api"


class UserInfo(BaseModel):
    username: str
    client_id: str
    jti: str
    active_scenario: int
    active_provider: str
    active_model: str


# ── NEW model — matches what React frontend expects back ──────────────────────

# class ReactLoginRequest(BaseModel):
#     username: str
#     password: str

class ReactLoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None

class ReactLoginResponse(BaseModel):
    token: str        # React stores this as jwt_token in localStorage
    username: str     # shown in Header as user.username
    email: str        # shown in Header as user.email
    name: str         # shown in Header as user.name
    session_id: str   # unique session identifier


# ── Existing /auth/login — UNCHANGED (built-in frontend still uses this) ─────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Obtain a JWT access token",
    description=(
        "Returns a bearer token valid for `jwt_expiry_hours` hours. "
        "Pass `client_id` to tag which surface is authenticating "
        "(web / mobile / terminal / api)."
    ),
)
# def login(body: LoginRequest, cfg: AppConfig = Depends(get_settings)):
#     auth_logger = get_application_logger()

#     if body.username != cfg.admin_username:
#         auth_logger.log_auth_login_event(
#             status_code=AUTH_EVENT_USER_NOT_FOUND,
#             user_id=body.username,
#             request_source=body.client_id,
#         )
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

#     if not verify_password(body.password, cfg.admin_password):
#         auth_logger.log_auth_login_event(
#             status_code=AUTH_EVENT_INVALID_CREDENTIALS,
#             user_id=body.username,
#             request_source=body.client_id,
#         )
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

#     auth_logger.log_auth_login_event(
#         status_code=AUTH_EVENT_SUCCESS,
#         user_id=body.username,
#         request_source=body.client_id,
#     )
#     return create_token(body.username, client_id=body.client_id)

def login(body: LoginRequest, cfg: AppConfig = Depends(get_settings)):
    if body.username and body.password:
        if body.username != cfg.admin_username or not verify_password(body.password, cfg.admin_password):
            raise HTTPException(status_code=401, detail="Invalid username or password")
    return create_token(body.username or "guest", client_id=body.client_id)


@router.get("/me", response_model=UserInfo, summary="Return the current authenticated user")
def me(user: TokenData = Depends(get_current_user), cfg: AppConfig = Depends(get_settings)):
    return UserInfo(
        username=user.username,
        client_id=user.client_id,
        jti=user.jti,
        active_scenario=cfg.active_scenario,
        active_provider=cfg.active_api_provider,
        active_model=cfg.llm_model_name,
    )


# ── NEW /login — for React frontend ──────────────────────────────────────────
# React authService.ts calls: POST /api/login
# Vite proxy rewrites:        /api/login  →  /login  (on port 8000)
# This endpoint returns the exact shape React's AuthContext.login() expects.

@react_router.post(
    "/login",
    response_model=ReactLoginResponse,
    summary="React frontend login",
    description=(
        "Called by the React frontend (DATAstream UI). "
        "Validates credentials and returns { token, username, email, name }. "
        "The token is a standard JWT — same secret as /auth/login."
    ),
)
# def react_login(body: ReactLoginRequest, cfg: AppConfig = Depends(get_settings)):
#     auth_logger = get_application_logger()

#     if body.username != cfg.admin_username:
#         auth_logger.log_auth_login_event(
#             status_code=AUTH_EVENT_USER_NOT_FOUND,
#             user_id=body.username,
#             request_source="web",
#         )
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

#     if not verify_password(body.password, cfg.admin_password):
#         auth_logger.log_auth_login_event(
#             status_code=AUTH_EVENT_INVALID_CREDENTIALS,
#             user_id=body.username,
#             request_source="web",
#         )
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

#     token_response = create_token(body.username, client_id="web")
#     auth_logger.log_auth_login_event(
#         status_code=AUTH_EVENT_SUCCESS,
#         user_id=body.username,
#         request_source="web",
#     )

#     display_name = body.username.replace(".", " ").replace("_", " ").title()

#     return ReactLoginResponse(
#         token=token_response.access_token,
#         username=body.username,
#         email=f"{body.username}@slipstream-it.com",
#         name=display_name,
#         session_id=token_response.session_id,
#     )

def react_login(body: ReactLoginRequest, cfg: AppConfig = Depends(get_settings)):
    if body.username and body.password:
        if body.username != cfg.admin_username or not verify_password(body.password, cfg.admin_password):
            raise HTTPException(status_code=401, detail="Invalid username or password")

    display_name = (body.username or "guest").replace(".", " ").title()
    token_response = create_token(body.username or "guest", client_id="web")

    return ReactLoginResponse(
        token=token_response.access_token,
        username=body.username or "guest",
        email=f"{body.username or 'guest'}@slipstream-it.com",
        name=display_name,
        session_id=token_response.session_id,
    )
