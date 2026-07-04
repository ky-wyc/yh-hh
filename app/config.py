from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_secret_key: str = Field(default="change-me", alias="APP_SECRET_KEY")
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="change-me", alias="ADMIN_PASSWORD")

    database_url: str = Field(default="sqlite+aiosqlite:///./data/qqbot.db", alias="DATABASE_URL")
    redis_url: str = Field(default="", alias="REDIS_URL")

    onebot_connection_mode: str = Field(default="reverse_ws", alias="ONEBOT_CONNECTION_MODE")
    onebot_reverse_ws_path: str = Field(default="/onebot/ws", alias="ONEBOT_REVERSE_WS_PATH")
    onebot_access_token: str = Field(default="", alias="ONEBOT_ACCESS_TOKEN")

    bot_qq: str = Field(default="", alias="BOT_QQ")
    bot_nicknames_raw: str = Field(default="bot,助手", alias="BOT_NICKNAMES")
    admin_qq_ids_raw: str = Field(default="", alias="ADMIN_QQ_IDS")
    command_prefix: str = Field(default="/", alias="COMMAND_PREFIX")
    allowed_groups_raw: str = Field(default="", alias="ALLOWED_GROUPS")
    default_group_enabled: bool = Field(default=True, alias="DEFAULT_GROUP_ENABLED")
    default_reply_mode: str = Field(default="mention_only", alias="DEFAULT_REPLY_MODE")

    llm_provider: str = Field(default="openai_compatible", alias="LLM_PROVIDER")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4.1-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.7, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=1000, alias="LLM_MAX_TOKENS")
    llm_timeout_seconds: float = Field(default=30, alias="LLM_TIMEOUT_SECONDS")

    rate_limit_per_user_per_minute: int = Field(default=12, alias="RATE_LIMIT_PER_USER_PER_MINUTE")
    rate_limit_per_group_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_GROUP_PER_MINUTE")

    @property
    def bot_nicknames(self) -> list[str]:
        return parse_csv(self.bot_nicknames_raw)

    @property
    def admin_qq_ids(self) -> set[str]:
        return set(parse_csv(self.admin_qq_ids_raw))

    @property
    def allowed_groups(self) -> set[str]:
        return set(parse_csv(self.allowed_groups_raw))


@lru_cache
def get_settings() -> Settings:
    return Settings()
