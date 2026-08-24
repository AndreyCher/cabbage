from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .settings import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


def require_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    if credentials is None or not secrets.compare_digest(credentials.credentials, settings.api_token):
        raise HTTPException(status_code=401, detail="invalid_token", headers={"WWW-Authenticate": "Bearer"})
