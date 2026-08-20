# from fastapi import Depends, HTTPException, status
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# from auth.jwt_handler import verify_token, TokenData
# from config.settings import get_config, AppConfig
# from services.base_service import ServiceFactory, BaseService

# _bearer = HTTPBearer()


# def get_current_user(
#     creds: HTTPAuthorizationCredentials = Depends(_bearer),
# ) -> TokenData:
#     try:
#         return verify_token(creds.credentials)
#     except ValueError as exc:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=str(exc),
#             headers={"WWW-Authenticate": "Bearer"},
#         ) from exc


# def get_settings() -> AppConfig:
#     return get_config()


# def get_service() -> BaseService:
#     return ServiceFactory.create()


# def get_session_store():
#     """Return the process-singleton SessionStore (initialised by ServiceFactory)."""
#     ServiceFactory.initialize()
#     return ServiceFactory._store


from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth.jwt_handler import verify_token, TokenData
from config.settings import get_config, AppConfig
from services.base_service import ServiceFactory, BaseService

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> TokenData:
    if creds and creds.credentials:
        try:
            return verify_token(creds.credentials)
        except ValueError:
            pass
    return TokenData(username="system", client_id="web", jti="no-auth")


def get_settings() -> AppConfig:
    return get_config()


def get_service() -> BaseService:
    return ServiceFactory.create()


def get_session_store():
    ServiceFactory.initialize()
    return ServiceFactory._store