from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse
from typing import Any

from pydantic import BaseModel, Field, field_validator


REPLY_MODES = {"disabled", "command_only", "mention_only", "active"}
MEMORY_STATUSES = {"pending", "approved", "rejected", "deleted"}
SCHEDULE_TYPES = {"once", "daily", "interval"}
TASK_TYPES = {"reminder_once", "daily_summary", "cleanup_context"}


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
    welcome_enabled: bool | None = None
    welcome_message: str | None = None
    flood_enabled: bool | None = None
    flood_message_count: int | None = Field(default=None, ge=3, le=50)
    flood_window_seconds: int | None = Field(default=None, ge=3, le=300)
    flood_mute_seconds: int | None = Field(default=None, ge=10, le=3600)

    @field_validator("reply_mode")
    @classmethod
    def validate_reply_mode(cls, value: str | None) -> str | None:
        if value is not None and value not in REPLY_MODES:
            raise ValueError(f"reply_mode must be one of: {', '.join(sorted(REPLY_MODES))}")
        return value

    @field_validator("welcome_message")
    @classmethod
    def validate_welcome_message(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if len(stripped) > 500:
            raise ValueError("welcome_message must be 500 characters or fewer")
        return stripped


class GroupModerationConfigOut(BaseModel):
    welcome_enabled: bool
    welcome_message: str
    flood_enabled: bool
    flood_message_count: int
    flood_window_seconds: int
    flood_mute_seconds: int


class SkillSettingOut(BaseModel):
    skill_name: str
    display_name: str
    description: str
    global_enabled: bool
    group_enabled: bool | None = None
    effective_enabled: bool


class SkillSettingUpdate(BaseModel):
    enabled: bool
    group_id: str = ""

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str) -> str:
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("group_id must be numeric or empty for global skill settings")
        return stripped


class GroupDetailOut(BaseModel):
    qq_group_id: str
    name: str
    enabled: bool
    reply_mode: str
    moderation: GroupModerationConfigOut
    overview: dict[str, int]
    skills: list[SkillSettingOut]


class KeywordRuleOut(BaseModel):
    id: int
    group_id: str
    keyword: str
    response: str
    enabled: bool
    created_by: str
    created_at: str


class KeywordRuleCreate(BaseModel):
    group_id: str = ""
    keyword: str
    response: str = "命中关键词，已记录。"
    enabled: bool = True

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str) -> str:
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("group_id must be numeric or empty for global rules")
        return stripped

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("keyword must not be empty")
        if len(stripped) > 255:
            raise ValueError("keyword must be 255 characters or fewer")
        return stripped

    @field_validator("response")
    @classmethod
    def validate_response(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("response must not be empty")
        if len(stripped) > 2000:
            raise ValueError("response must be 2000 characters or fewer")
        return stripped


class KeywordRuleUpdate(BaseModel):
    group_id: str | None = None
    keyword: str | None = None
    response: str | None = None
    enabled: bool | None = None

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("group_id must be numeric or empty for global rules")
        return stripped

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("keyword must not be empty")
        if len(stripped) > 255:
            raise ValueError("keyword must be 255 characters or fewer")
        return stripped

    @field_validator("response")
    @classmethod
    def validate_response(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("response must not be empty")
        if len(stripped) > 2000:
            raise ValueError("response must be 2000 characters or fewer")
        return stripped


class MemoryOut(BaseModel):
    id: int
    group_id: str
    user_id: str
    content: str
    source: str
    confidence: float
    status: str
    created_by: str
    created_at: str
    updated_at: str


class MemoryCreate(BaseModel):
    group_id: str = ""
    user_id: str = ""
    content: str
    source: str = "admin"
    confidence: float = Field(default=0.8, ge=0, le=1)
    status: str = "approved"

    @field_validator("group_id", "user_id")
    @classmethod
    def validate_optional_numeric_id(cls, value: str) -> str:
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("value must be numeric or empty")
        return stripped

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be empty")
        if len(stripped) > 2000:
            raise ValueError("content must be 2000 characters or fewer")
        return stripped

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("source must not be empty")
        if len(stripped) > 64:
            raise ValueError("source must be 64 characters or fewer")
        return stripped

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in MEMORY_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(MEMORY_STATUSES))}")
        return value


class MemoryUpdate(BaseModel):
    group_id: str | None = None
    user_id: str | None = None
    content: str | None = None
    source: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: str | None = None

    @field_validator("group_id", "user_id")
    @classmethod
    def validate_optional_numeric_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("value must be numeric or empty")
        return stripped

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be empty")
        if len(stripped) > 2000:
            raise ValueError("content must be 2000 characters or fewer")
        return stripped

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("source must not be empty")
        if len(stripped) > 64:
            raise ValueError("source must be 64 characters or fewer")
        return stripped

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in MEMORY_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(MEMORY_STATUSES))}")
        return value


class KnowledgeDocumentOut(BaseModel):
    id: int
    group_id: str
    title: str
    content: str
    enabled: bool
    index_status: str
    index_error: str
    chunk_count: int
    created_by: str
    created_at: str
    updated_at: str


class KnowledgeDocumentCreate(BaseModel):
    group_id: str = ""
    title: str
    content: str
    enabled: bool = True

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str) -> str:
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("group_id must be numeric or empty for global knowledge")
        return stripped

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        if len(stripped) > 255:
            raise ValueError("title must be 255 characters or fewer")
        return stripped

    @field_validator("content")
    @classmethod
    def validate_knowledge_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be empty")
        if len(stripped) > 200000:
            raise ValueError("content must be 200000 characters or fewer")
        return stripped


class KnowledgeDocumentUpdate(BaseModel):
    group_id: str | None = None
    title: str | None = None
    content: str | None = None
    enabled: bool | None = None

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("group_id must be numeric or empty for global knowledge")
        return stripped

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        if len(stripped) > 255:
            raise ValueError("title must be 255 characters or fewer")
        return stripped

    @field_validator("content")
    @classmethod
    def validate_knowledge_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be empty")
        if len(stripped) > 200000:
            raise ValueError("content must be 200000 characters or fewer")
        return stripped


class KnowledgeSearchRequest(BaseModel):
    group_id: str = ""
    query: str
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str) -> str:
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("group_id must be numeric or empty")
        return stripped

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        if len(stripped) > 1000:
            raise ValueError("query must be 1000 characters or fewer")
        return stripped


class ScheduledTaskOut(BaseModel):
    id: int
    name: str
    task_type: str
    schedule_type: str
    group_id: str
    user_id: str
    payload: dict[str, Any]
    enabled: bool
    next_run_at: str | None
    interval_seconds: int
    last_run_at: str | None
    created_by: str
    created_at: str
    updated_at: str


class ScheduledTaskCreate(BaseModel):
    name: str
    task_type: str
    schedule_type: str
    group_id: str = ""
    user_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    next_run_at: datetime | None = None
    interval_seconds: int = Field(default=0, ge=0, le=60 * 60 * 24 * 30)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        if len(stripped) > 255:
            raise ValueError("name must be 255 characters or fewer")
        return stripped

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        if value not in TASK_TYPES:
            raise ValueError(f"task_type must be one of: {', '.join(sorted(TASK_TYPES))}")
        return value

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, value: str) -> str:
        if value not in SCHEDULE_TYPES:
            raise ValueError(f"schedule_type must be one of: {', '.join(sorted(SCHEDULE_TYPES))}")
        return value

    @field_validator("group_id", "user_id")
    @classmethod
    def validate_optional_id(cls, value: str) -> str:
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("value must be numeric or empty")
        return stripped


class ScheduledTaskUpdate(BaseModel):
    name: str | None = None
    task_type: str | None = None
    schedule_type: str | None = None
    group_id: str | None = None
    user_id: str | None = None
    payload: dict[str, Any] | None = None
    enabled: bool | None = None
    next_run_at: datetime | None = None
    interval_seconds: int | None = Field(default=None, ge=0, le=60 * 60 * 24 * 30)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        if len(stripped) > 255:
            raise ValueError("name must be 255 characters or fewer")
        return stripped

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str | None) -> str | None:
        if value is not None and value not in TASK_TYPES:
            raise ValueError(f"task_type must be one of: {', '.join(sorted(TASK_TYPES))}")
        return value

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, value: str | None) -> str | None:
        if value is not None and value not in SCHEDULE_TYPES:
            raise ValueError(f"schedule_type must be one of: {', '.join(sorted(SCHEDULE_TYPES))}")
        return value

    @field_validator("group_id", "user_id")
    @classmethod
    def validate_optional_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if stripped and not stripped.isdigit():
            raise ValueError("value must be numeric or empty")
        return stripped


class TaskRunOut(BaseModel):
    id: int
    task_id: int
    task_type: str
    group_id: str
    status: str
    result_message: str
    error_message: str
    started_at: str
    finished_at: str | None


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
