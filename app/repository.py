from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, parse_csv
from app.models import AuditLog, BotReply, Group, KeywordRule, LLMUsageLog, MessageLog, Setting, User


@dataclass(slots=True)
class LLMConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: float


@dataclass(slots=True)
class BotConfig:
    default_group_enabled: bool
    default_reply_mode: str
    command_prefix: str
    bot_qq: str
    bot_nicknames: str
    admin_qq_ids: str
    allowed_groups: str
    rate_limit_per_user_per_minute: int
    rate_limit_per_group_per_minute: int

    @property
    def bot_nickname_list(self) -> list[str]:
        return parse_csv(self.bot_nicknames)

    @property
    def admin_qq_id_set(self) -> set[str]:
        return set(parse_csv(self.admin_qq_ids))

    @property
    def allowed_group_set(self) -> set[str]:
        return set(parse_csv(self.allowed_groups))


class Repository:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings

    async def ensure_user(self, qq_id: str, nickname: str = "") -> User:
        result = await self.session.execute(select(User).where(User.qq_id == qq_id))
        bot_settings = await self.get_bot_settings()
        admin_qq_ids = bot_settings.admin_qq_id_set
        user = result.scalar_one_or_none()
        if user:
            if nickname and user.nickname != nickname:
                user.nickname = nickname
            if qq_id in admin_qq_ids and user.role == "normal_user":
                user.role = "super_admin"
            return user
        role = "super_admin" if qq_id in admin_qq_ids else "normal_user"
        user = User(qq_id=qq_id, nickname=nickname, role=role)
        self.session.add(user)
        await self.session.flush()
        return user

    async def ensure_group(self, qq_group_id: str, name: str = "") -> Group:
        result = await self.session.execute(select(Group).where(Group.qq_group_id == qq_group_id))
        group = result.scalar_one_or_none()
        if group:
            if name and group.name != name:
                group.name = name
            return group
        bot_settings = await self.get_bot_settings()
        group = Group(
            qq_group_id=qq_group_id,
            name=name,
            enabled=bot_settings.default_group_enabled,
            reply_mode=bot_settings.default_reply_mode,
        )
        self.session.add(group)
        await self.session.flush()
        return group

    async def get_groups(self) -> list[Group]:
        result = await self.session.execute(select(Group).order_by(Group.qq_group_id))
        return list(result.scalars().all())

    async def update_group(self, qq_group_id: str, **changes: Any) -> Group:
        group = await self.ensure_group(qq_group_id)
        for key, value in changes.items():
            if value is not None and hasattr(group, key):
                setattr(group, key, value)
        await self.session.flush()
        return group

    async def save_message(
        self,
        *,
        group_id: str,
        user_id: str,
        message_id: str,
        dedup_key: str,
        content: str,
        raw_event: dict[str, Any],
        status: str = "received",
        drop_reason: str = "",
    ) -> tuple[MessageLog | None, bool]:
        result = await self.session.execute(select(MessageLog).where(MessageLog.dedup_key == dedup_key))
        if result.scalar_one_or_none() is not None:
            return None, True

        log = MessageLog(
            group_id=group_id,
            user_id=user_id,
            message_id=message_id,
            dedup_key=dedup_key,
            content=content,
            raw_event_json=json.dumps(raw_event, ensure_ascii=False),
            status=status,
            drop_reason=drop_reason,
        )
        self.session.add(log)
        await self.session.flush()
        return log, False

    async def mark_message(self, message_log: MessageLog | None, status: str, reason: str = "") -> None:
        if message_log is None:
            return
        message_log.status = status
        message_log.drop_reason = reason
        await self.session.flush()

    async def save_reply(
        self,
        *,
        group_id: str,
        user_id: str,
        trigger_type: str,
        content: str,
        skill_name: str,
        input_message_id: str = "",
        llm_model: str = "",
    ) -> BotReply:
        reply = BotReply(
            group_id=group_id,
            user_id=user_id,
            trigger_type=trigger_type,
            content=content,
            skill_name=skill_name,
            input_message_id=input_message_id,
            llm_model=llm_model,
        )
        self.session.add(reply)
        await self.session.flush()
        return reply

    async def get_setting(self, key: str) -> str | None:
        result = await self.session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        return setting.value if setting else None

    async def set_setting(self, key: str, value: str) -> None:
        result = await self.session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting is None:
            self.session.add(Setting(key=key, value=value))
        else:
            setting.value = value
        await self.session.flush()

    async def get_llm_config(self) -> LLMConfig:
        async def val(key: str, default: str) -> str:
            stored = await self.get_setting(key)
            return default if stored is None else stored

        return LLMConfig(
            provider=await val("llm_provider", self.settings.llm_provider),
            base_url=await val("llm_base_url", self.settings.llm_base_url),
            api_key=await val("llm_api_key", self.settings.llm_api_key),
            model=await val("llm_model", self.settings.llm_model),
            temperature=float(await val("llm_temperature", str(self.settings.llm_temperature))),
            max_tokens=int(await val("llm_max_tokens", str(self.settings.llm_max_tokens))),
            timeout_seconds=float(
                await val("llm_timeout_seconds", str(self.settings.llm_timeout_seconds))
            ),
        )

    async def update_llm_config(self, changes: dict[str, Any]) -> None:
        key_map = {
            "provider": "llm_provider",
            "base_url": "llm_base_url",
            "api_key": "llm_api_key",
            "model": "llm_model",
            "temperature": "llm_temperature",
            "max_tokens": "llm_max_tokens",
            "timeout_seconds": "llm_timeout_seconds",
        }
        for field, value in changes.items():
            if value is not None and field in key_map:
                await self.set_setting(key_map[field], str(value))

    async def get_bot_settings(self) -> BotConfig:
        async def val(key: str, default: str) -> str:
            stored = await self.get_setting(key)
            return default if stored is None else stored

        default_group_enabled = await val("default_group_enabled", str(self.settings.default_group_enabled))
        return BotConfig(
            default_group_enabled=(
                default_group_enabled.lower() == "true"
            ),
            default_reply_mode=await val("default_reply_mode", self.settings.default_reply_mode),
            command_prefix=await val("command_prefix", self.settings.command_prefix),
            bot_qq=await val("bot_qq", self.settings.bot_qq),
            bot_nicknames=await val("bot_nicknames", self.settings.bot_nicknames_raw),
            admin_qq_ids=await val("admin_qq_ids", self.settings.admin_qq_ids_raw),
            allowed_groups=await val("allowed_groups", self.settings.allowed_groups_raw),
            rate_limit_per_user_per_minute=int(
                await val("rate_limit_per_user_per_minute", str(self.settings.rate_limit_per_user_per_minute))
            ),
            rate_limit_per_group_per_minute=int(
                await val("rate_limit_per_group_per_minute", str(self.settings.rate_limit_per_group_per_minute))
            ),
        )

    async def update_bot_settings(self, changes: dict[str, Any]) -> None:
        key_map = {
            "default_group_enabled": "default_group_enabled",
            "default_reply_mode": "default_reply_mode",
            "command_prefix": "command_prefix",
            "bot_qq": "bot_qq",
            "bot_nicknames": "bot_nicknames",
            "admin_qq_ids": "admin_qq_ids",
            "allowed_groups": "allowed_groups",
            "rate_limit_per_user_per_minute": "rate_limit_per_user_per_minute",
            "rate_limit_per_group_per_minute": "rate_limit_per_group_per_minute",
        }
        for field, value in changes.items():
            if value is not None and field in key_map:
                await self.set_setting(key_map[field], str(value))

    async def add_keyword_rule(
        self, *, group_id: str, keyword: str, response: str, created_by: str
    ) -> KeywordRule:
        result = await self.session.execute(
            select(KeywordRule).where(KeywordRule.group_id == group_id, KeywordRule.keyword == keyword)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.response = response
            existing.created_by = created_by
            existing.enabled = True
            await self.session.flush()
            return existing

        rule = KeywordRule(
            group_id=group_id,
            keyword=keyword,
            response=response,
            created_by=created_by,
        )
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def create_or_update_keyword_rule(
        self,
        *,
        group_id: str,
        keyword: str,
        response: str,
        enabled: bool,
        created_by: str,
    ) -> tuple[KeywordRule, bool]:
        result = await self.session.execute(
            select(KeywordRule).where(KeywordRule.group_id == group_id, KeywordRule.keyword == keyword)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.response = response
            existing.enabled = enabled
            if created_by:
                existing.created_by = created_by
            await self.session.flush()
            return existing, False

        rule = KeywordRule(
            group_id=group_id,
            keyword=keyword,
            response=response,
            enabled=enabled,
            created_by=created_by,
        )
        self.session.add(rule)
        await self.session.flush()
        return rule, True

    async def get_keyword_rule_by_id(self, rule_id: int) -> KeywordRule | None:
        result = await self.session.execute(select(KeywordRule).where(KeywordRule.id == rule_id))
        return result.scalar_one_or_none()

    async def list_keyword_rules_for_admin(self, group_id: str | None = None) -> list[KeywordRule]:
        query = select(KeywordRule)
        if group_id is not None:
            query = query.where(KeywordRule.group_id == group_id)
        result = await self.session.execute(query.order_by(KeywordRule.group_id, KeywordRule.keyword))
        return list(result.scalars().all())

    async def update_keyword_rule_by_id(self, rule_id: int, changes: dict[str, Any]) -> KeywordRule | None:
        rule = await self.get_keyword_rule_by_id(rule_id)
        if rule is None:
            return None

        next_group_id = changes.get("group_id", rule.group_id)
        next_keyword = changes.get("keyword", rule.keyword)
        if next_group_id != rule.group_id or next_keyword != rule.keyword:
            result = await self.session.execute(
                select(KeywordRule).where(
                    KeywordRule.group_id == next_group_id,
                    KeywordRule.keyword == next_keyword,
                    KeywordRule.id != rule_id,
                )
            )
            if result.scalar_one_or_none() is not None:
                raise ValueError("keyword rule already exists for this group")

        for key in ("group_id", "keyword", "response", "enabled"):
            if key in changes and changes[key] is not None:
                setattr(rule, key, changes[key])
        await self.session.flush()
        return rule

    async def delete_keyword_rule_by_id(self, rule_id: int) -> int:
        result = await self.session.execute(delete(KeywordRule).where(KeywordRule.id == rule_id))
        await self.session.flush()
        return result.rowcount or 0

    async def delete_keyword_rule(self, *, group_id: str, keyword: str) -> int:
        result = await self.session.execute(
            delete(KeywordRule).where(KeywordRule.group_id == group_id, KeywordRule.keyword == keyword)
        )
        await self.session.flush()
        return result.rowcount or 0

    async def list_keyword_rules(self, group_id: str) -> list[KeywordRule]:
        result = await self.session.execute(
            select(KeywordRule).where(
                KeywordRule.enabled.is_(True),
                (KeywordRule.group_id == group_id) | (KeywordRule.group_id == ""),
            )
        )
        return list(result.scalars().all())

    async def find_keyword_hit(self, group_id: str, content: str) -> KeywordRule | None:
        for rule in await self.list_keyword_rules(group_id):
            if rule.keyword and rule.keyword in content:
                return rule
        return None

    async def audit(
        self,
        *,
        action: str,
        actor_user_id: str = "",
        actor_role: str = "",
        group_id: str = "",
        target_type: str = "",
        target_id: str = "",
        detail: dict[str, Any] | None = None,
        result: str = "success",
    ) -> None:
        self.session.add(
            AuditLog(
                action=action,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                group_id=group_id,
                target_type=target_type,
                target_id=target_id,
                detail_json=json.dumps(detail or {}, ensure_ascii=False),
                result=result,
            )
        )
        await self.session.flush()

    async def save_llm_usage(
        self,
        *,
        config: LLMConfig,
        group_id: str = "",
        user_id: str = "",
        skill_name: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
        status: str = "success",
        error_message: str = "",
    ) -> None:
        self.session.add(
            LLMUsageLog(
                group_id=group_id,
                user_id=user_id,
                skill_name=skill_name,
                provider=config.provider,
                model=config.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status=status,
                error_message=error_message[:1000],
            )
        )
        await self.session.flush()

    async def recent_messages(self, limit: int = 50) -> list[MessageLog]:
        result = await self.session.execute(select(MessageLog).order_by(MessageLog.id.desc()).limit(limit))
        return list(result.scalars().all())

    async def recent_errors(self, limit: int = 50) -> list[MessageLog]:
        result = await self.session.execute(
            select(MessageLog)
            .where(MessageLog.status.in_(["dropped", "error"]))
            .order_by(MessageLog.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def recent_llm_usage(self, limit: int = 50) -> list[LLMUsageLog]:
        result = await self.session.execute(
            select(LLMUsageLog).order_by(LLMUsageLog.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def recent_audit_logs(self, limit: int = 50) -> list[AuditLog]:
        result = await self.session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))
        return list(result.scalars().all())

    async def overview(self) -> dict[str, Any]:
        messages = await self.session.scalar(select(func.count(MessageLog.id)))
        replies = await self.session.scalar(select(func.count(BotReply.id)))
        groups = await self.session.scalar(select(func.count(Group.id)).where(Group.enabled.is_(True)))
        llm_calls = await self.session.scalar(select(func.count(LLMUsageLog.id)))
        return {
            "messages": messages or 0,
            "replies": replies or 0,
            "enabled_groups": groups or 0,
            "llm_calls": llm_calls or 0,
        }
