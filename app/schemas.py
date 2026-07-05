from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


REPLY_MODES = {"disabled", "command_only", "mention_only", "active"}


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

    @field_validator("reply_mode")
    @classmethod
    def validate_reply_mode(cls, value: str | None) -> str | None:
        if value is not None and value not in REPLY_MODES:
            raise ValueError(f"reply_mode must be one of: {', '.join(sorted(REPLY_MODES))}")
        return value


class BotSettingsOut(BaseModel):
    default_group_enabled: bool
    default_reply_mode: str
    command_prefix: str
    bot_qq: str
    bot_nicknames: str
    admin_qq_ids: str
    allowed_groups: str
    rate_limit_per_user_per_minute: int
    rate_limit_per_group_per_minute: int


class BotSettingsUpdate(BaseModel):
    default_group_enabled: bool | None = None
    default_reply_mode: str | None = None
    command_prefix: str | None = None
    bot_qq: str | None = None
    bot_nicknames: str | None = None
    admin_qq_ids: str | None = None
    allowed_groups: str | None = None
    rate_limit_per_user_per_minute: int | None = Field(default=None, ge=1, le=600)
    rate_limit_per_group_per_minute: int | None = Field(default=None, ge=1, le=3000)

    @field_validator("default_reply_mode")
    @classmethod
    def validate_default_reply_mode(cls, value: str | None) -> str | None:
        if value is not None and value not in REPLY_MODES:
            raise ValueError(f"default_reply_mode must be one of: {', '.join(sorted(REPLY_MODES))}")
        return value

    @field_validator("command_prefix")
    @classmethod
    def validate_command_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("command_prefix must not be empty")
        if len(value) > 8:
            raise ValueError("command_prefix must be 8 characters or fewer")
        if any(char.isspace() for char in value):
            raise ValueError("command_prefix must not contain whitespace")
        return value

    @field_validator("bot_qq")
    @classmethod
    def validate_optional_qq_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("bot_qq must be numeric")
        return stripped

    @field_validator("admin_qq_ids", "allowed_groups")
    @classmethod
    def validate_numeric_csv(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if any(not part.isdigit() for part in parts):
            raise ValueError("value must be comma-separated numeric ids")
        return ",".join(parts)

    @field_validator("bot_nicknames")
    @classmethod
    def validate_bot_nicknames(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if any(len(part) > 32 for part in parts):
            raise ValueError("each bot nickname must be 32 characters or fewer")
        return ",".join(parts)


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
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)
    timeout_seconds: float | None = Field(default=None, ge=1, le=300)

    @field_validator("provider", "model")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("value must not be empty")
        return value.strip() if value is not None else value

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        parsed = urlparse(stripped)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("base_url must start with http:// or https://")
        if not parsed.hostname:
            raise ValueError("base_url must include a host")
        return stripped


class LLMTestRequest(BaseModel):
    prompt: str = "ping"
