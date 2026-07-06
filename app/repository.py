from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, parse_csv
from app.knowledge import chunk_text, knowledge_score
from app.models import (
    AuditLog,
    BotReply,
    GameState,
    Group,
    KeywordRule,
    KnowledgeChunk,
    KnowledgeDocument,
    LLMUsageLog,
    MemoryRecord,
    MessageLog,
    ScheduledTask,
    Setting,
    SkillSetting,
    TaskRun,
    User,
    now_utc,
)


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


@dataclass(slots=True)
class GroupModerationConfig:
    welcome_enabled: bool = False
    welcome_message: str = "欢迎 {user_id} 加入本群。"
    flood_enabled: bool = False
    flood_message_count: int = 6
    flood_window_seconds: int = 10
    flood_mute_seconds: int = 60


@dataclass(slots=True)
class KnowledgeSearchResult:
    document_id: int
    chunk_id: int
    title: str
    group_id: str
    chunk_index: int
    content: str
    score: float

    @property
    def source(self) -> str:
        return f"{self.title}#{self.chunk_index + 1}"


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

    async def get_group_by_qq_id(self, qq_group_id: str) -> Group | None:
        result = await self.session.execute(select(Group).where(Group.qq_group_id == qq_group_id))
        return result.scalar_one_or_none()

    async def update_group(self, qq_group_id: str, **changes: Any) -> Group:
        group = await self.ensure_group(qq_group_id)
        for key, value in changes.items():
            if value is not None and hasattr(group, key):
                setattr(group, key, value)
        await self.session.flush()
        return group

    def group_moderation_config(self, group: Group) -> GroupModerationConfig:
        try:
            config = json.loads(group.config_json or "{}")
            if not isinstance(config, dict):
                config = {}
        except json.JSONDecodeError:
            config = {}
        moderation = config.get("moderation") if isinstance(config.get("moderation"), dict) else {}
        return GroupModerationConfig(
            welcome_enabled=bool(moderation.get("welcome_enabled", False)),
            welcome_message=str(
                moderation.get("welcome_message") or "欢迎 {user_id} 加入本群。"
            )[:500],
            flood_enabled=bool(moderation.get("flood_enabled", False)),
            flood_message_count=max(3, min(int(moderation.get("flood_message_count") or 6), 50)),
            flood_window_seconds=max(
                3, min(int(moderation.get("flood_window_seconds") or 10), 300)
            ),
            flood_mute_seconds=max(
                10, min(int(moderation.get("flood_mute_seconds") or 60), 3600)
            ),
        )

    async def update_group_moderation_config(
        self,
        qq_group_id: str,
        changes: dict[str, Any],
    ) -> Group:
        group = await self.ensure_group(qq_group_id)
        try:
            config = json.loads(group.config_json or "{}")
            if not isinstance(config, dict):
                config = {}
        except json.JSONDecodeError:
            config = {}
        moderation = config.get("moderation") if isinstance(config.get("moderation"), dict) else {}
        for key, value in changes.items():
            if value is not None:
                moderation[key] = value
        config["moderation"] = moderation
        group.config_json = json.dumps(config, ensure_ascii=False)
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

    async def get_skill_setting(self, *, skill_name: str, group_id: str = "") -> SkillSetting | None:
        result = await self.session.execute(
            select(SkillSetting).where(
                SkillSetting.group_id == group_id,
                SkillSetting.skill_name == skill_name,
            )
        )
        return result.scalar_one_or_none()

    async def set_skill_enabled(
        self,
        *,
        skill_name: str,
        enabled: bool,
        group_id: str = "",
        updated_by: str = "",
    ) -> SkillSetting:
        setting = await self.get_skill_setting(skill_name=skill_name, group_id=group_id)
        if setting is None:
            setting = SkillSetting(
                skill_name=skill_name,
                group_id=group_id,
                enabled=enabled,
                updated_by=updated_by,
            )
            self.session.add(setting)
        else:
            setting.enabled = enabled
            setting.updated_by = updated_by
        await self.session.flush()
        return setting

    async def skill_settings_for_group(self, group_id: str) -> dict[str, bool | None]:
        result = await self.session.execute(select(SkillSetting).where(SkillSetting.group_id == group_id))
        return {item.skill_name: item.enabled for item in result.scalars().all()}

    async def effective_skill_enabled(self, *, skill_name: str, group_id: str) -> bool:
        global_setting = await self.get_skill_setting(skill_name=skill_name, group_id="")
        if global_setting is not None and not global_setting.enabled:
            return False
        group_setting = await self.get_skill_setting(skill_name=skill_name, group_id=group_id)
        if group_setting is not None:
            return group_setting.enabled
        return True

    async def enabled_skill_names(self, group_id: str, skill_names: list[str]) -> set[str]:
        enabled = set()
        for skill_name in skill_names:
            if await self.effective_skill_enabled(skill_name=skill_name, group_id=group_id):
                enabled.add(skill_name)
        return enabled

    async def group_overview(self, group_id: str) -> dict[str, int]:
        messages = await self.session.scalar(
            select(func.count(MessageLog.id)).where(MessageLog.group_id == group_id)
        )
        replies = await self.session.scalar(
            select(func.count(BotReply.id)).where(BotReply.group_id == group_id)
        )
        memories = await self.session.scalar(
            select(func.count(MemoryRecord.id)).where(
                MemoryRecord.group_id == group_id,
                MemoryRecord.status != "deleted",
            )
        )
        knowledge_docs = await self.session.scalar(
            select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.group_id == group_id)
        )
        keyword_rules = await self.session.scalar(
            select(func.count(KeywordRule.id)).where(KeywordRule.group_id == group_id)
        )
        scheduled_tasks = await self.session.scalar(
            select(func.count(ScheduledTask.id)).where(ScheduledTask.group_id == group_id)
        )
        active_games = await self.session.scalar(
            select(func.count(GameState.id)).where(
                GameState.group_id == group_id,
                GameState.status == "active",
                GameState.expires_at > now_utc(),
            )
        )
        return {
            "messages": messages or 0,
            "replies": replies or 0,
            "memories": memories or 0,
            "knowledge_docs": knowledge_docs or 0,
            "keyword_rules": keyword_rules or 0,
            "scheduled_tasks": scheduled_tasks or 0,
            "active_games": active_games or 0,
        }

    async def active_game(self, *, group_id: str, game_name: str = "guess") -> GameState | None:
        await self.expire_game_states()
        result = await self.session.execute(
            select(GameState)
            .where(
                GameState.group_id == group_id,
                GameState.game_name == game_name,
                GameState.status == "active",
                GameState.expires_at > now_utc(),
            )
            .order_by(GameState.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_guess_game(
        self,
        *,
        group_id: str,
        user_id: str,
        secret: int,
        expires_in_hours: int = 24,
    ) -> GameState:
        if await self.active_game(group_id=group_id, game_name="guess") is not None:
            raise ValueError("active guess game already exists")
        state = GameState(
            group_id=group_id,
            game_name="guess",
            status="active",
            state_json=json.dumps({"secret": secret, "attempts": 0}, ensure_ascii=False),
            started_by=user_id,
            expires_at=now_utc() + timedelta(hours=expires_in_hours),
        )
        self.session.add(state)
        await self.session.flush()
        return state

    async def update_game_state(
        self,
        game: GameState,
        *,
        state: dict[str, Any] | None = None,
        status: str | None = None,
        winner_user_id: str | None = None,
    ) -> GameState:
        if state is not None:
            game.state_json = json.dumps(state, ensure_ascii=False)
        if status is not None:
            game.status = status
        if winner_user_id is not None:
            game.winner_user_id = winner_user_id
        await self.session.flush()
        return game

    async def stop_active_game(self, *, group_id: str, game_name: str = "guess") -> GameState | None:
        game = await self.active_game(group_id=group_id, game_name=game_name)
        if game is None:
            return None
        game.status = "stopped"
        await self.session.flush()
        return game

    async def expire_game_states(self, now: datetime | None = None) -> int:
        now = now or now_utc()
        result = await self.session.execute(
            select(GameState).where(GameState.status == "active", GameState.expires_at <= now)
        )
        expired = list(result.scalars().all())
        for game in expired:
            game.status = "expired"
        await self.session.flush()
        return len(expired)

    async def create_memory(
        self,
        *,
        content: str,
        group_id: str = "",
        user_id: str = "",
        source: str = "admin",
        confidence: float = 0.8,
        status: str = "pending",
        created_by: str = "",
    ) -> MemoryRecord:
        memory = MemoryRecord(
            group_id=group_id,
            user_id=user_id,
            content=content,
            source=source,
            confidence=confidence,
            status=status,
            created_by=created_by,
        )
        self.session.add(memory)
        await self.session.flush()
        return memory

    async def list_memories_for_admin(
        self,
        *,
        status: str | None = None,
        group_id: str | None = None,
        user_id: str | None = None,
        limit: int = 200,
    ) -> list[MemoryRecord]:
        query = select(MemoryRecord)
        if status:
            query = query.where(MemoryRecord.status == status)
        if group_id is not None:
            query = query.where(MemoryRecord.group_id == group_id)
        if user_id is not None:
            query = query.where(MemoryRecord.user_id == user_id)
        result = await self.session.execute(query.order_by(MemoryRecord.id.desc()).limit(limit))
        return list(result.scalars().all())

    async def get_memory_by_id(self, memory_id: int) -> MemoryRecord | None:
        result = await self.session.execute(select(MemoryRecord).where(MemoryRecord.id == memory_id))
        return result.scalar_one_or_none()

    async def update_memory_by_id(self, memory_id: int, changes: dict[str, Any]) -> MemoryRecord | None:
        memory = await self.get_memory_by_id(memory_id)
        if memory is None:
            return None
        for key in ("group_id", "user_id", "content", "source", "confidence", "status", "created_by"):
            if key in changes and changes[key] is not None:
                setattr(memory, key, changes[key])
        await self.session.flush()
        return memory

    async def approved_memories_for_context(
        self,
        *,
        group_id: str,
        user_id: str,
        limit: int = 8,
    ) -> list[MemoryRecord]:
        result = await self.session.execute(
            select(MemoryRecord)
            .where(
                MemoryRecord.status == "approved",
                or_(MemoryRecord.group_id == "", MemoryRecord.group_id == group_id),
                or_(MemoryRecord.user_id == "", MemoryRecord.user_id == user_id),
            )
            .order_by(MemoryRecord.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_knowledge_document(
        self,
        *,
        group_id: str,
        title: str,
        content: str,
        enabled: bool,
        created_by: str,
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(
            group_id=group_id,
            title=title,
            content=content,
            enabled=enabled,
            created_by=created_by,
        )
        self.session.add(document)
        await self.session.flush()
        await self.rebuild_knowledge_chunks(document)
        return document

    async def get_knowledge_document_by_id(self, document_id: int) -> KnowledgeDocument | None:
        result = await self.session.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        return result.scalar_one_or_none()

    async def list_knowledge_documents(self, group_id: str | None = None) -> list[KnowledgeDocument]:
        query = select(KnowledgeDocument)
        if group_id is not None:
            query = query.where(KnowledgeDocument.group_id == group_id)
        result = await self.session.execute(query.order_by(KnowledgeDocument.id.desc()))
        return list(result.scalars().all())

    async def update_knowledge_document_by_id(
        self,
        document_id: int,
        changes: dict[str, Any],
    ) -> KnowledgeDocument | None:
        document = await self.get_knowledge_document_by_id(document_id)
        if document is None:
            return None
        content_changed = False
        scope_changed = False
        for key in ("group_id", "title", "content", "enabled"):
            if key in changes and changes[key] is not None:
                if key == "content" and changes[key] != document.content:
                    content_changed = True
                if key in {"group_id", "title"} and changes[key] != getattr(document, key):
                    scope_changed = True
                setattr(document, key, changes[key])
        await self.session.flush()
        if content_changed or scope_changed:
            await self.rebuild_knowledge_chunks(document)
        return document

    async def delete_knowledge_document_by_id(self, document_id: int) -> int:
        document = await self.get_knowledge_document_by_id(document_id)
        if document is None:
            return 0
        await self.session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
        result = await self.session.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
        await self.session.flush()
        return result.rowcount or 0

    async def rebuild_knowledge_chunks(self, document: KnowledgeDocument) -> None:
        await self.session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
        try:
            chunks = chunk_text(document.content)
            for index, content in enumerate(chunks):
                self.session.add(
                    KnowledgeChunk(
                        document_id=document.id,
                        group_id=document.group_id,
                        title=document.title,
                        chunk_index=index,
                        content=content,
                    )
                )
            document.chunk_count = len(chunks)
            document.index_status = "completed"
            document.index_error = ""
        except Exception as exc:
            document.chunk_count = 0
            document.index_status = "failed"
            document.index_error = str(exc)[:1000]
        await self.session.flush()

    async def search_knowledge(
        self,
        *,
        group_id: str,
        query: str,
        limit: int = 5,
    ) -> list[KnowledgeSearchResult]:
        result = await self.session.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(
                KnowledgeDocument.enabled.is_(True),
                KnowledgeDocument.index_status == "completed",
                or_(KnowledgeChunk.group_id == "", KnowledgeChunk.group_id == group_id),
            )
        )
        ranked: list[KnowledgeSearchResult] = []
        for chunk, document in result.all():
            score = knowledge_score(query, chunk.content)
            if score <= 0:
                continue
            ranked.append(
                KnowledgeSearchResult(
                    document_id=document.id,
                    chunk_id=chunk.id,
                    title=chunk.title,
                    group_id=chunk.group_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    score=score,
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:limit]

    async def create_scheduled_task(
        self,
        *,
        name: str,
        task_type: str,
        schedule_type: str,
        group_id: str = "",
        user_id: str = "",
        payload: dict[str, Any] | None = None,
        enabled: bool = True,
        next_run_at: datetime | None = None,
        interval_seconds: int = 0,
        created_by: str = "",
    ) -> ScheduledTask:
        task = ScheduledTask(
            name=name,
            task_type=task_type,
            schedule_type=schedule_type,
            group_id=group_id,
            user_id=user_id,
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
            enabled=enabled,
            next_run_at=next_run_at,
            interval_seconds=interval_seconds,
            created_by=created_by,
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def get_scheduled_task_by_id(self, task_id: int) -> ScheduledTask | None:
        result = await self.session.execute(select(ScheduledTask).where(ScheduledTask.id == task_id))
        return result.scalar_one_or_none()

    async def list_scheduled_tasks(self, group_id: str | None = None) -> list[ScheduledTask]:
        query = select(ScheduledTask)
        if group_id is not None:
            query = query.where(ScheduledTask.group_id == group_id)
        result = await self.session.execute(query.order_by(ScheduledTask.id.desc()))
        return list(result.scalars().all())

    async def update_scheduled_task_by_id(
        self,
        task_id: int,
        changes: dict[str, Any],
    ) -> ScheduledTask | None:
        task = await self.get_scheduled_task_by_id(task_id)
        if task is None:
            return None
        if "payload" in changes and changes["payload"] is not None:
            task.payload_json = json.dumps(changes.pop("payload"), ensure_ascii=False)
        for key in (
            "name",
            "task_type",
            "schedule_type",
            "group_id",
            "user_id",
            "enabled",
            "next_run_at",
            "interval_seconds",
            "created_by",
        ):
            if key in changes and changes[key] is not None:
                setattr(task, key, changes[key])
        await self.session.flush()
        return task

    async def delete_scheduled_task_by_id(self, task_id: int) -> int:
        result = await self.session.execute(delete(ScheduledTask).where(ScheduledTask.id == task_id))
        await self.session.flush()
        return result.rowcount or 0

    async def due_scheduled_tasks(self, now: datetime, limit: int = 20) -> list[ScheduledTask]:
        result = await self.session.execute(
            select(ScheduledTask)
            .where(
                ScheduledTask.enabled.is_(True),
                ScheduledTask.next_run_at.is_not(None),
                ScheduledTask.next_run_at <= now,
            )
            .order_by(ScheduledTask.next_run_at, ScheduledTask.id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_task_run(
        self,
        *,
        task_id: int,
        task_type: str,
        group_id: str = "",
        status: str,
        result_message: str = "",
        error_message: str = "",
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> TaskRun:
        run = TaskRun(
            task_id=task_id,
            task_type=task_type,
            group_id=group_id,
            status=status,
            result_message=result_message,
            error_message=error_message[:1000],
            started_at=started_at or now_utc(),
            finished_at=finished_at,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def list_task_runs(self, task_id: int | None = None, limit: int = 100) -> list[TaskRun]:
        query = select(TaskRun)
        if task_id is not None:
            query = query.where(TaskRun.task_id == task_id)
        result = await self.session.execute(query.order_by(TaskRun.id.desc()).limit(limit))
        return list(result.scalars().all())

    async def recent_group_messages(self, group_id: str, since: datetime, limit: int = 50) -> list[MessageLog]:
        result = await self.session.execute(
            select(MessageLog)
            .where(MessageLog.group_id == group_id, MessageLog.created_at >= since)
            .order_by(MessageLog.id.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def recent_user_message_count(
        self,
        *,
        group_id: str,
        user_id: str,
        since: datetime,
    ) -> int:
        count = await self.session.scalar(
            select(func.count(MessageLog.id)).where(
                MessageLog.group_id == group_id,
                MessageLog.user_id == user_id,
                MessageLog.created_at >= since,
                MessageLog.status.in_(["received", "handled", "observed"]),
            )
        )
        return count or 0

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
