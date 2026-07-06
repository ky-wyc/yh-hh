from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from app.cache import RateLimitExceeded
from app.config import Settings
from app.events import BotEvent, GroupNoticeEvent
from app.image_generation import ImageGenerationService
from app.llm import LLMService
from app.models import now_utc
from app.repository import Repository
from app.scheduler import maybe_create_memory_summary_by_count
from app.skills import PRIVATE_SUPPORTED_SKILLS, SkillContext, SkillRegistry


@dataclass(slots=True)
class RouteOutcome:
    status: str
    reason: str = ""
    replied: bool = False
    reply_text: str = ""
    skill_name: str = ""


class MessageRouter:
    def __init__(
        self,
        settings: Settings,
        llm: LLMService,
        rate_limiter,
        image: ImageGenerationService | None = None,
    ):
        self.settings = settings
        self.llm = llm
        self.image = image or ImageGenerationService()
        self.rate_limiter = rate_limiter
        self.skills = SkillRegistry(self.image)

    async def handle(self, event: BotEvent, repo: Repository, sender) -> RouteOutcome:
        if event.message_type == "private":
            return await self.handle_private(event, repo, sender)

        message_log, duplicate = await repo.save_message(
            group_id=event.group_id,
            user_id=event.user_id,
            message_id=event.message_id,
            dedup_key=event.dedup_key,
            content=event.text,
            raw_event=event.raw,
            message_type=event.message_type,
        )
        if duplicate:
            return RouteOutcome(status="dropped", reason="duplicate")

        bot_settings = await repo.get_bot_settings()

        bot_qq = bot_settings.bot_qq or self.settings.bot_qq or event.self_id
        if bot_qq and event.user_id == bot_qq:
            await repo.mark_message(message_log, "dropped", "bot_self_message")
            return RouteOutcome(status="dropped", reason="bot_self_message")

        allowed_groups = bot_settings.allowed_group_set
        if allowed_groups and event.group_id not in allowed_groups:
            await repo.mark_message(message_log, "dropped", "group_not_allowed")
            return RouteOutcome(status="dropped", reason="group_not_allowed")

        user = await repo.ensure_user(event.user_id, event.nickname)
        group = await repo.ensure_group(event.group_id)

        if not group.enabled:
            await repo.mark_message(message_log, "dropped", "group_disabled")
            return RouteOutcome(status="dropped", reason="group_disabled")

        if group.reply_mode == "disabled":
            await repo.mark_message(message_log, "dropped", "reply_mode_disabled")
            return RouteOutcome(status="dropped", reason="reply_mode_disabled")

        try:
            await self.rate_limiter.check(
                f"group:{event.group_id}", bot_settings.rate_limit_per_group_per_minute
            )
            await self.rate_limiter.check(
                f"user:{event.user_id}", bot_settings.rate_limit_per_user_per_minute
            )
        except RateLimitExceeded as exc:
            await repo.mark_message(message_log, "dropped", f"rate_limited:{exc}")
            return RouteOutcome(status="dropped", reason="rate_limited")

        flood_outcome = await self._handle_flood_control(
            event,
            message_log,
            repo,
            sender,
            user_role=user.role,
        )
        if flood_outcome is not None:
            return flood_outcome

        await self.rate_limiter.append_context(
            event.group_id,
            f"{event.nickname or event.user_id}: {event.text}",
        )
        if bot_settings.memory_summary_by_count_enabled:
            try:
                await maybe_create_memory_summary_by_count(
                    repo,
                    self.llm,
                    event.group_id,
                    bot_settings.memory_summary_message_threshold,
                )
            except Exception as exc:
                await repo.audit(
                    action="memory_summary_count_failed",
                    group_id=event.group_id,
                    target_type="memory",
                    result="failed",
                    detail={"error": str(exc)[:500]},
                )

        command = self._parse_command(event.text, bot_settings.command_prefix)
        if command:
            name, args = command
            skill_name = self.skills.command_skill_name(name)
            enabled_skills = await repo.enabled_skill_names(event.group_id, self.skills.skill_names)
            if skill_name is not None and skill_name not in enabled_skills:
                text = f"该功能已关闭：{skill_name}"
                if not await self._send_group_reply(event, message_log, repo, sender, text):
                    return RouteOutcome(status="error", reason="send_failed")
                await repo.save_reply(
                    group_id=event.group_id,
                    user_id=event.user_id,
                    trigger_type="command_disabled",
                    input_message_id=event.message_id,
                    content=text,
                    skill_name=skill_name,
                )
                await repo.mark_message(message_log, "handled", f"skill_disabled:{skill_name}")
                return RouteOutcome(
                    status="handled",
                    reason="skill_disabled",
                    replied=True,
                    reply_text=text,
                    skill_name=skill_name,
                )
            recent_context = await self.rate_limiter.get_context(event.group_id)
            result = await self.skills.dispatch(
                name,
                args,
                SkillContext(
                    repo=repo,
                    llm=self.llm,
                    image=self.image,
                    group_id=event.group_id,
                    user_id=event.user_id,
                    message_id=event.message_id,
                    command_prefix=bot_settings.command_prefix,
                    recent_context=recent_context,
                    enabled_skills=enabled_skills,
                    sender=sender,
                ),
            )
            if not await self._send_group_reply(event, message_log, repo, sender, result.text):
                return RouteOutcome(status="error", reason="send_failed")
            await repo.save_reply(
                group_id=event.group_id,
                user_id=event.user_id,
                trigger_type="command",
                input_message_id=event.message_id,
                content=result.text,
                skill_name=result.skill_name,
                llm_model=result.llm_model,
            )
            await repo.mark_message(message_log, "handled", f"command:{name}")
            return RouteOutcome(
                status="handled",
                replied=True,
                reply_text=result.text,
                skill_name=result.skill_name,
            )

        admin_lite_enabled = await repo.effective_skill_enabled(
            skill_name="admin-lite",
            group_id=event.group_id,
        )
        keyword_hit = await repo.find_keyword_hit(event.group_id, event.text) if admin_lite_enabled else None
        if keyword_hit:
            if not await self._send_group_reply(
                event, message_log, repo, sender, keyword_hit.response
            ):
                return RouteOutcome(status="error", reason="send_failed")
            await repo.save_reply(
                group_id=event.group_id,
                user_id=event.user_id,
                trigger_type="keyword",
                input_message_id=event.message_id,
                content=keyword_hit.response,
                skill_name="admin-lite",
            )
            await repo.mark_message(message_log, "handled", "keyword_hit")
            return RouteOutcome(
                status="handled",
                replied=True,
                reply_text=keyword_hit.response,
                skill_name="admin-lite",
            )

        at_bot = (
            event.at_bot
            or self._has_runtime_at(event.text, bot_qq)
            or any(name and name in event.text for name in bot_settings.bot_nickname_list)
        )
        ai_enabled = await repo.effective_skill_enabled(skill_name="ai", group_id=event.group_id)
        if at_bot and group.reply_mode in {"mention_only", "active"} and ai_enabled:
            prompt = self._remove_bot_mentions(event.text, bot_qq, bot_settings.bot_nickname_list) or event.text
            context = await self.rate_limiter.get_context(event.group_id)
            prompt_with_context = self._with_context(prompt, context)
            llm_result = await self.llm.chat(
                repo,
                prompt_with_context,
                group_id=event.group_id,
                user_id=event.user_id,
                skill_name="mention_chat",
            )
            if not await self._send_group_reply(event, message_log, repo, sender, llm_result.text):
                return RouteOutcome(status="error", reason="send_failed")
            await repo.save_reply(
                group_id=event.group_id,
                user_id=event.user_id,
                trigger_type="mention_chat",
                input_message_id=event.message_id,
                content=llm_result.text,
                skill_name="ai",
                llm_model=llm_result.model,
            )
            await repo.mark_message(message_log, "handled", "mention_chat")
            return RouteOutcome(
                status="handled",
                replied=True,
                reply_text=llm_result.text,
                skill_name="ai",
            )

        if group.reply_mode == "active" and ai_enabled and self._looks_like_question(event.text):
            context = await self.rate_limiter.get_context(event.group_id)
            prompt_with_context = self._with_context(event.text, context)
            llm_result = await self.llm.chat(
                repo,
                prompt_with_context,
                group_id=event.group_id,
                user_id=event.user_id,
                skill_name="active_chat",
            )
            if not await self._send_group_reply(event, message_log, repo, sender, llm_result.text):
                return RouteOutcome(status="error", reason="send_failed")
            await repo.save_reply(
                group_id=event.group_id,
                user_id=event.user_id,
                trigger_type="active_chat",
                input_message_id=event.message_id,
                content=llm_result.text,
                skill_name="ai",
                llm_model=llm_result.model,
            )
            await repo.mark_message(message_log, "handled", "active_chat")
            return RouteOutcome(
                status="handled",
                replied=True,
                reply_text=llm_result.text,
                skill_name="ai",
            )

        await repo.mark_message(message_log, "observed", "no_trigger")
        return RouteOutcome(status="observed", reason="no_trigger")

    async def handle_private(self, event: BotEvent, repo: Repository, sender) -> RouteOutcome:
        message_log, duplicate = await repo.save_message(
            group_id="",
            user_id=event.user_id,
            message_id=event.message_id,
            dedup_key=event.dedup_key,
            content=event.text,
            raw_event=event.raw,
            message_type="private",
        )
        if duplicate:
            return RouteOutcome(status="dropped", reason="duplicate")

        bot_settings = await repo.get_bot_settings()
        bot_qq = bot_settings.bot_qq or self.settings.bot_qq or event.self_id
        if bot_qq and event.user_id == bot_qq:
            await repo.mark_message(message_log, "dropped", "bot_self_message")
            return RouteOutcome(status="dropped", reason="bot_self_message")

        if not bot_settings.private_chat_enabled:
            await repo.mark_message(message_log, "dropped", "private_chat_disabled")
            return RouteOutcome(status="dropped", reason="private_chat_disabled")

        whitelist = bot_settings.private_chat_whitelist_set
        if not whitelist or event.user_id not in whitelist:
            await repo.mark_message(message_log, "dropped", "private_user_not_allowed")
            return RouteOutcome(status="dropped", reason="private_user_not_allowed")

        await repo.ensure_user(event.user_id, event.nickname)
        try:
            await self.rate_limiter.check(
                f"private_user:{event.user_id}", bot_settings.rate_limit_per_user_per_minute
            )
        except RateLimitExceeded as exc:
            await repo.mark_message(message_log, "dropped", f"rate_limited:{exc}")
            return RouteOutcome(status="dropped", reason="rate_limited")

        context_key = f"private:{event.user_id}"
        await self.rate_limiter.append_context(context_key, f"{event.nickname or event.user_id}: {event.text}")

        command = self._parse_command(event.text, bot_settings.command_prefix)
        enabled_skills = (
            await repo.enabled_skill_names("", self.skills.skill_names)
        ).intersection(PRIVATE_SUPPORTED_SKILLS)
        if command:
            name, args = command
            skill_name = self.skills.command_skill_name(name)
            if skill_name is not None and skill_name not in PRIVATE_SUPPORTED_SKILLS:
                text = f"该功能不支持私聊：{skill_name}"
                if not await self._send_private_reply(event, message_log, repo, sender, text):
                    return RouteOutcome(status="error", reason="send_failed")
                await repo.save_reply(
                    group_id="",
                    user_id=event.user_id,
                    trigger_type="private_command_unsupported",
                    input_message_id=event.message_id,
                    content=text,
                    skill_name=skill_name,
                )
                await repo.mark_message(message_log, "handled", f"private_skill_unsupported:{skill_name}")
                return RouteOutcome(
                    status="handled",
                    reason="private_skill_unsupported",
                    replied=True,
                    reply_text=text,
                    skill_name=skill_name,
                )
            if skill_name is not None and skill_name not in enabled_skills:
                text = f"该功能已关闭：{skill_name}"
                if not await self._send_private_reply(event, message_log, repo, sender, text):
                    return RouteOutcome(status="error", reason="send_failed")
                await repo.save_reply(
                    group_id="",
                    user_id=event.user_id,
                    trigger_type="private_command_disabled",
                    input_message_id=event.message_id,
                    content=text,
                    skill_name=skill_name,
                )
                await repo.mark_message(message_log, "handled", f"skill_disabled:{skill_name}")
                return RouteOutcome(
                    status="handled",
                    reason="skill_disabled",
                    replied=True,
                    reply_text=text,
                    skill_name=skill_name,
                )
            recent_context = await self.rate_limiter.get_context(context_key)
            result = await self.skills.dispatch(
                name,
                args,
                SkillContext(
                    repo=repo,
                    llm=self.llm,
                    image=self.image,
                    group_id="",
                    user_id=event.user_id,
                    message_id=event.message_id,
                    command_prefix=bot_settings.command_prefix,
                    recent_context=recent_context,
                    enabled_skills=enabled_skills,
                    sender=sender,
                ),
            )
            if not await self._send_private_reply(event, message_log, repo, sender, result.text):
                return RouteOutcome(status="error", reason="send_failed")
            await repo.save_reply(
                group_id="",
                user_id=event.user_id,
                trigger_type="private_command",
                input_message_id=event.message_id,
                content=result.text,
                skill_name=result.skill_name,
                llm_model=result.llm_model,
            )
            await repo.mark_message(message_log, "handled", f"private_command:{name}")
            return RouteOutcome(
                status="handled",
                replied=True,
                reply_text=result.text,
                skill_name=result.skill_name,
            )

        if "ai" not in enabled_skills:
            await repo.mark_message(message_log, "observed", "private_ai_disabled")
            return RouteOutcome(status="observed", reason="private_ai_disabled")

        context = await self.rate_limiter.get_context(context_key)
        prompt_with_context = self._with_context(event.text, context)
        llm_result = await self.llm.chat(
            repo,
            prompt_with_context,
            group_id="",
            user_id=event.user_id,
            skill_name="private_chat",
        )
        if not await self._send_private_reply(event, message_log, repo, sender, llm_result.text):
            return RouteOutcome(status="error", reason="send_failed")
        await repo.save_reply(
            group_id="",
            user_id=event.user_id,
            trigger_type="private_chat",
            input_message_id=event.message_id,
            content=llm_result.text,
            skill_name="ai",
            llm_model=llm_result.model,
        )
        await repo.mark_message(message_log, "handled", "private_chat")
        return RouteOutcome(
            status="handled",
            replied=True,
            reply_text=llm_result.text,
            skill_name="ai",
        )

    async def handle_group_notice(
        self,
        event: GroupNoticeEvent,
        repo: Repository,
        sender: Any,
    ) -> RouteOutcome:
        bot_settings = await repo.get_bot_settings()
        allowed_groups = bot_settings.allowed_group_set
        if allowed_groups and event.group_id not in allowed_groups:
            return RouteOutcome(status="dropped", reason="group_not_allowed")

        group = await repo.ensure_group(event.group_id)
        if not group.enabled:
            return RouteOutcome(status="dropped", reason="group_disabled")

        config = repo.group_moderation_config(group)
        if not config.welcome_enabled:
            return RouteOutcome(status="observed", reason="welcome_disabled")
        if not await repo.effective_skill_enabled(skill_name="admin-lite", group_id=event.group_id):
            return RouteOutcome(status="observed", reason="admin_lite_disabled")

        text = (
            config.welcome_message.replace("{user_id}", event.user_id).replace(
                "{group_id}", event.group_id
            )
        )
        try:
            await sender.send_group_message(event.group_id, text)
        except Exception:
            return RouteOutcome(status="error", reason="send_failed")

        await repo.audit(
            action="welcome_new_member",
            actor_role="system",
            group_id=event.group_id,
            target_type="user",
            target_id=event.user_id,
        )
        return RouteOutcome(
            status="handled",
            reason="welcome",
            replied=True,
            reply_text=text,
            skill_name="admin-lite",
        )

    async def _handle_flood_control(
        self,
        event: BotEvent,
        message_log: Any,
        repo: Repository,
        sender: Any,
        *,
        user_role: str,
    ) -> RouteOutcome | None:
        if user_role in {"super_admin", "group_admin"}:
            return None
        if not await repo.effective_skill_enabled(skill_name="admin-lite", group_id=event.group_id):
            return None
        group = await repo.get_group_by_qq_id(event.group_id)
        if group is None:
            return None
        config = repo.group_moderation_config(group)
        if not config.flood_enabled:
            return None
        since = now_utc() - timedelta(seconds=config.flood_window_seconds)
        count = await repo.recent_user_message_count(
            group_id=event.group_id,
            user_id=event.user_id,
            since=since,
        )
        if count < config.flood_message_count:
            return None

        violation_since = now_utc() - timedelta(hours=config.violation_window_hours)
        previous_violations = await repo.moderation_violation_count(
            group_id=event.group_id,
            user_id=event.user_id,
            since=violation_since,
        )
        violation_count = previous_violations + 1
        mute_seconds = config.flood_mute_seconds
        if config.escalation_enabled:
            mute_seconds = min(
                config.escalation_max_mute_seconds,
                config.flood_mute_seconds
                * (config.escalation_multiplier ** max(0, previous_violations)),
            )

        try:
            if hasattr(sender, "mute_user"):
                await sender.mute_user(event.group_id, event.user_id, mute_seconds)
            text = f"检测到刷屏，已临时禁言 {mute_seconds} 秒。"
            if config.escalation_enabled and previous_violations > 0:
                text += f" 近期累计违规 {violation_count} 次。"
            await sender.send_group_message(event.group_id, text)
        except Exception as exc:
            await repo.mark_message(message_log, "error", f"flood_mute_failed:{type(exc).__name__}")
            return RouteOutcome(status="error", reason="send_failed")

        await repo.audit(
            action="flood_mute",
            actor_role="system",
            group_id=event.group_id,
            target_type="user",
            target_id=event.user_id,
            detail={
                "message_count": count,
                "window_seconds": config.flood_window_seconds,
                "mute_seconds": mute_seconds,
                "base_mute_seconds": config.flood_mute_seconds,
                "violation_count": violation_count,
                "escalation_enabled": config.escalation_enabled,
            },
        )
        await repo.save_reply(
            group_id=event.group_id,
            user_id=event.user_id,
            trigger_type="flood_control",
            input_message_id=event.message_id,
            content=text,
            skill_name="admin-lite",
        )
        await repo.mark_message(message_log, "handled", "flood_mute")
        return RouteOutcome(
            status="handled",
            reason="flood_mute",
            replied=True,
            reply_text=text,
            skill_name="admin-lite",
        )

    async def _send_group_reply(
        self,
        event: BotEvent,
        message_log: Any,
        repo: Repository,
        sender: Any,
        text: str,
    ) -> bool:
        try:
            await sender.send_group_message(event.group_id, text)
        except Exception as exc:
            await repo.mark_message(message_log, "error", f"send_failed:{type(exc).__name__}")
            return False
        return True

    async def _send_private_reply(
        self,
        event: BotEvent,
        message_log: Any,
        repo: Repository,
        sender: Any,
        text: str,
    ) -> bool:
        try:
            await sender.send_private_message(event.user_id, text)
        except Exception as exc:
            await repo.mark_message(message_log, "error", f"send_failed:{type(exc).__name__}")
            return False
        return True

    def _parse_command(self, text: str, prefix: str | None = None) -> tuple[str, str] | None:
        command_prefix = prefix or self.settings.command_prefix
        if not text.startswith(command_prefix):
            return None
        payload = text[len(command_prefix) :].strip()
        if not payload:
            return None
        name, _, args = payload.partition(" ")
        return name.lower(), args.strip()

    @staticmethod
    def _looks_like_question(text: str) -> bool:
        normalized = text.strip()
        if not normalized:
            return False
        if normalized.endswith(("?", "？")):
            return True
        question_markers = (
            "吗",
            "么",
            "嘛",
            "什么",
            "怎么",
            "怎样",
            "如何",
            "为什么",
            "为何",
            "哪",
            "谁",
            "几点",
            "多少",
            "能不能",
            "可不可以",
            "是不是",
            "有没有",
        )
        return any(marker in normalized for marker in question_markers)

    @staticmethod
    def _with_context(prompt: str, context: list[str]) -> str:
        if not context:
            return prompt
        return "最近上下文：\n" + "\n".join(context[-10:]) + f"\n\n当前问题：{prompt}"

    @staticmethod
    def _remove_bot_mentions(text: str, bot_qq: str, bot_nicknames: list[str]) -> str:
        cleaned = text
        if bot_qq:
            cleaned = cleaned.replace(f"[CQ:at,qq={bot_qq}]", "")
        for name in bot_nicknames:
            cleaned = cleaned.replace(name, "")
        return cleaned.strip()

    @staticmethod
    def _has_runtime_at(text: str, bot_qq: str) -> bool:
        return bool(bot_qq and f"[CQ:at,qq={bot_qq}]" in text)
