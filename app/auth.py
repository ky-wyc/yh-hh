from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings


security = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class TokenStore:
    tokens: set[str] = field(default_factory=set)

    def issue(self) -> str:
        token = secrets.token_urlsafe(32)
        self.tokens.add(token)
        return token

    def validate(self, token: str) -> bool:
        return token in self.tokens


def login(settings: Settings, store: TokenStore, username: str, password: str) -> str:
    if not secrets.compare_digest(username, settings.admin_username):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not secrets.compare_digest(password, settings.admin_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return store.issue()


async def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    store: TokenStore = request.app.state.token_store
    if not store.validate(credentials.credentials):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

