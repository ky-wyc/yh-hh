from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.cache import RateLimitExceeded
from app.config import Settings
from app.events import BotEvent
from app.llm import LLMService
from app.repository import Repository
from app.skills import SkillContext, SkillRegistry


@dataclass(slots=True)
class RouteOutcome:
    status: str
    reason: str = ""
    replied: bool = False
    reply_text: str = ""
    skill_name: str = ""


class MessageRouter:
    def __init__(self, settings: Settings, llm: LLMService, rate_limiter):
        self.settings = settings
        self.llm = llm
        self.rate_limiter = rate_limiter
        self.skills = SkillRegistry()

    async def handle(self, event: BotEvent, repo: Repository, sender) -> RouteOutcome:
        message_log, duplicate = await repo.save_message(
            group_id=event.group_id,
            user_id=event.user_id,
            message_id=event.message_id,
            dedup_key=event.dedup_key,
            content=event.text,
            raw_event=event.raw,
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

        await repo.ensure_user(event.user_id, event.nickname)
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

        await self.rate_limiter.append_context(
            event.group_id,
            f"{event.nickname or event.user_id}: {event.text}",
        )

        command = self._parse_command(event.text, bot_settings.command_prefix)
        if command:
            name, args = command
            recent_context = await self.rate_limiter.get_context(event.group_id)
            result = await self.skills.dispatch(
                name,
                args,
                SkillContext(
                    repo=repo,
                    llm=self.llm,
                    group_id=event.group_id,
                    user_id=event.user_id,
                    message_id=event.message_id,
                    command_prefix=bot_settings.command_prefix,
                    recent_context=recent_context,
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

        keyword_hit = await repo.find_keyword_hit(event.group_id, event.text)
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
        if at_bot and group.reply_mode in {"mention_only", "active"}:
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

        if group.reply_mode == "active" and self._looks_like_question(event.text):
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
        return "最近群聊上下文：\n" + "\n".join(context[-10:]) + f"\n\n当前问题：{prompt}"

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
