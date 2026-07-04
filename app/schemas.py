from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GroupUpdate(BaseModel):
    enabled: bool | None = None
    reply_mode: str | None = None
    name: str | None = None


class LLMSettingsOut(BaseModel):
    provider: str
    base_url: str
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: float
    api_key_configured: bool


class LLMSettingsUpdate(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = Field(default=None)
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_seconds: float | None = None


class LLMTestRequest(BaseModel):
    prompt: str = "ping"

