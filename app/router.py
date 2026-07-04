from __future__ import annotations

from dataclasses import dataclass

from app.cache import RateLimitExceeded
from app.config import Settings
from app.events import BotEvent, remove_bot_mentions
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

        await repo.ensure_user(event.user_id, event.nickname)
        group = await repo.ensure_group(event.group_id)

        if self.settings.allowed_groups and event.group_id not in self.settings.allowed_groups:
            await repo.mark_message(message_log, "dropped", "group_not_allowed")
            return RouteOutcome(status="dropped", reason="group_not_allowed")

        if not group.enabled:
            await repo.mark_message(message_log, "dropped", "group_disabled")
            return RouteOutcome(status="dropped", reason="group_disabled")

        try:
            await self.rate_limiter.check(
                f"group:{event.group_id}", self.settings.rate_limit_per_group_per_minute
            )
            await self.rate_limiter.check(
                f"user:{event.user_id}", self.settings.rate_limit_per_user_per_minute
            )
        except RateLimitExceeded as exc:
            await repo.mark_message(message_log, "dropped", f"rate_limited:{exc}")
            return RouteOutcome(status="dropped", reason="rate_limited")

        command = self._parse_command(event.text)
        if command:
            name, args = command
            result = await self.skills.dispatch(
                name,
                args,
                SkillContext(
                    repo=repo,
                    llm=self.llm,
                    group_id=event.group_id,
                    user_id=event.user_id,
                    message_id=event.message_id,
                ),
            )
            await sender.send_group_message(event.group_id, result.text)
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
            await sender.send_group_message(event.group_id, keyword_hit.response)
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

        if event.at_bot and group.reply_mode in {"mention_only", "active"}:
            prompt = remove_bot_mentions(event.text, self.settings) or event.text
            llm_result = await self.llm.chat(
                repo,
                prompt,
                group_id=event.group_id,
                user_id=event.user_id,
                skill_name="mention_chat",
            )
            await sender.send_group_message(event.group_id, llm_result.text)
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

        await repo.mark_message(message_log, "observed", "no_trigger")
        return RouteOutcome(status="observed", reason="no_trigger")

    def _parse_command(self, text: str) -> tuple[str, str] | None:
        if not text.startswith(self.settings.command_prefix):
            return None
        payload = text[len(self.settings.command_prefix) :].strip()
        if not payload:
            return None
        name, _, args = payload.partition(" ")
        return name.lower(), args.strip()

