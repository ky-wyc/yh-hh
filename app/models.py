from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    qq_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(32), default="normal_user")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    qq_group_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reply_mode: Mapped[str] = mapped_column(String(32), default="mention_only")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc)


class MessageLog(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    message_id: Mapped[str] = mapped_column(String(128), default="")
    dedup_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    message_type: Mapped[str] = mapped_column(String(32), default="group")
    content: Mapped[str] = mapped_column(Text, default="")
    raw_event_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="received")
    drop_reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class BotReply(Base):
    __tablename__ = "bot_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    trigger_type: Mapped[str] = mapped_column(String(64), default="")
    input_message_id: Mapped[str] = mapped_column(String(128), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    skill_name: Mapped[str] = mapped_column(String(64), default="")
    llm_model: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc)


class KeywordRule(Base):
    __tablename__ = "keyword_rules"
    __table_args__ = (UniqueConstraint("group_id", "keyword", name="uq_keyword_group"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    keyword: Mapped[str] = mapped_column(String(255))
    response: Mapped[str] = mapped_column(Text, default="命中关键词，已记录。")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[str] = mapped_column(String(64), default="")
    actor_role: Mapped[str] = mapped_column(String(64), default="")
    group_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    target_type: Mapped[str] = mapped_column(String(64), default="")
    target_id: Mapped[str] = mapped_column(String(128), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    result: Mapped[str] = mapped_column(String(64), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class LLMUsageLog(Base):
    __tablename__ = "llm_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    skill_name: Mapped[str] = mapped_column(String(64), default="")
    provider: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(64), default="success")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
