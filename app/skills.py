from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from app.image_generation import ImageGenerationService
from app.llm import LLMService
from app.models import now_utc
from app.repository import Repository
from app.web_search import (
    WebSearchService,
    format_search_context,
    should_auto_web_search,
    with_search_context,
)


SKILL_CATALOG: dict[str, dict[str, Any]] = {
    "help": {
        "display_name": "帮助",
        "description": "查看机器人可用命令。",
        "category": "基础",
        "commands": ["help"],
        "risk_level": "low",
        "requires_admin": False,
        "uses_llm": False,
        "uses_knowledge": False,
        "uses_memory": False,
        "private_supported": True,
    },
    "ping": {
        "display_name": "健康检查",
        "description": "检查机器人是否在线。",
        "category": "基础",
        "commands": ["ping"],
        "risk_level": "low",
        "requires_admin": False,
        "uses_llm": False,
        "uses_knowledge": False,
        "uses_memory": False,
        "private_supported": True,
    },
    "ai": {
        "display_name": "AI 问答",
        "description": "大模型聊天、@ 回复和主动回答。",
        "category": "AI",
        "commands": ["ai"],
        "risk_level": "medium",
        "requires_admin": False,
        "uses_llm": True,
        "uses_knowledge": False,
        "uses_memory": True,
        "private_supported": True,
    },
    "kb": {
        "display_name": "知识库",
        "description": "查询后台维护的群知识库。",
        "category": "AI",
        "commands": ["kb"],
        "risk_level": "medium",
        "requires_admin": False,
        "uses_llm": True,
        "uses_knowledge": True,
        "uses_memory": False,
        "private_supported": True,
    },
    "image": {
        "display_name": "生图",
        "description": "使用独立生图模型生成图片。",
        "category": "AI",
        "commands": ["image", "draw"],
        "risk_level": "medium",
        "requires_admin": False,
        "uses_llm": True,
        "uses_knowledge": False,
        "uses_memory": False,
        "private_supported": True,
    },
    "web-search": {
        "display_name": "\u8054\u7f51\u641c\u7d22",
        "description": "\u81ea\u52a8\u5224\u65ad\u5b9e\u65f6\u95ee\u9898\u5e76\u5148\u8054\u7f51\u641c\u7d22\u518d\u56de\u7b54\u3002",
        "category": "AI",
        "commands": ["search", "web", "\u8054\u7f51", "\u641c\u7d22"],
        "risk_level": "medium",
        "requires_admin": False,
        "uses_llm": True,
        "uses_knowledge": False,
        "uses_memory": False,
        "private_supported": True,
    },
    "dice": {
        "display_name": "掷骰子",
        "description": "娱乐掷骰子命令。",
        "category": "娱乐",
        "commands": ["dice"],
        "risk_level": "low",
        "requires_admin": False,
        "uses_llm": False,
        "uses_knowledge": False,
        "uses_memory": False,
        "private_supported": True,
    },
    "guess": {
        "display_name": "猜数字",
        "description": "按群持久保存的猜数字游戏。",
        "category": "娱乐",
        "commands": ["guess"],
        "risk_level": "low",
        "requires_admin": False,
        "uses_llm": False,
        "uses_knowledge": False,
        "uses_memory": False,
        "private_supported": False,
    },
    "memory": {
        "display_name": "长期记忆",
        "description": "手动记住和忘记待审核记忆。",
        "category": "记忆",
        "commands": ["remember", "forget"],
        "risk_level": "medium",
        "requires_admin": False,
        "uses_llm": False,
        "uses_knowledge": False,
        "uses_memory": True,
        "private_supported": True,
    },
    "admin-lite": {
        "display_name": "基础群管",
        "description": "警告、关键词拦截和轻量群管命令。",
        "category": "群管",
        "commands": ["warn", "banword", "mute", "unmute"],
        "risk_level": "high",
        "requires_admin": True,
        "uses_llm": False,
        "uses_knowledge": False,
        "uses_memory": False,
        "private_supported": False,
    },
}

PRIVATE_SUPPORTED_SKILLS = {
    name for name, item in SKILL_CATALOG.items() if item.get("private_supported")
}

COMMAND_SKILLS: dict[str, str] = {
    "help": "help",
    "ping": "ping",
    "ai": "ai",
    "kb": "kb",
    "image": "image",
    "draw": "image",
    "search": "web-search",
    "web": "web-search",
    "\u8054\u7f51": "web-search",
    "\u641c\u7d22": "web-search",
    "dice": "dice",
    "guess": "guess",
    "remember": "memory",
    "forget": "memory",
    "warn": "admin-lite",
    "banword": "admin-lite",
    "mute": "admin-lite",
    "unmute": "admin-lite",
}


@dataclass(slots=True)
class SkillContext:
    repo: Repository
    llm: LLMService
    image: ImageGenerationService
    group_id: str
    user_id: str
    web_search: WebSearchService | None = None
    message_id: str = ""
    command_prefix: str = "/"
    recent_context: list[str] | None = None
    enabled_skills: set[str] | None = None
    sender: object | None = None


@dataclass(slots=True)
class SkillResult:
    text: str
    skill_name: str
    llm_model: str = ""


class SkillRegistry:
    def __init__(
        self,
        image: ImageGenerationService | None = None,
        web_search: WebSearchService | None = None,
    ):
        self.image = image or ImageGenerationService()
        self.web_search = web_search or WebSearchService()
        self._handlers = {
            "help": self.help,
            "ping": self.ping,
            "ai": self.ai,
            "kb": self.kb,
            "image": self.image_generate,
            "draw": self.image_generate,
            "search": self.web_search_answer,
            "web": self.web_search_answer,
            "\u8054\u7f51": self.web_search_answer,
            "\u641c\u7d22": self.web_search_answer,
            "dice": self.dice,
            "guess": self.guess,
            "remember": self.remember,
            "forget": self.forget,
            "warn": self.warn,
            "banword": self.banword,
            "mute": self.mute,
            "unmute": self.unmute,
        }

    @property
    def names(self) -> list[str]:
        return sorted(self._handlers)

    @property
    def skill_names(self) -> list[str]:
        return sorted(SKILL_CATALOG)

    def command_skill_name(self, command_name: str) -> str | None:
        return COMMAND_SKILLS.get(command_name)

    async def dispatch(self, name: str, args: str, ctx: SkillContext) -> SkillResult:
        handler = self._handlers.get(name)
        if handler is None:
            return SkillResult(
                text=f"未知命令：{ctx.command_prefix}{name}。发送 {ctx.command_prefix}help 查看可用命令。",
                skill_name="unknown",
            )
        return await handler(args, ctx)

    async def help(self, args: str, ctx: SkillContext) -> SkillResult:
        prefix = ctx.command_prefix
        enabled = ctx.enabled_skills if ctx.enabled_skills is not None else set(SKILL_CATALOG)
        lines = ["可用命令："]
        if "help" in enabled:
            lines.append(f"{prefix}help - 查看帮助")
        if "ping" in enabled:
            lines.append(f"{prefix}ping - 健康检查")
        if "ai" in enabled:
            lines.append(f"{prefix}ai 问题 - 向大模型提问")
        if "kb" in enabled:
            lines.append(f"{prefix}kb 问题 - 查询知识库")
        if "image" in enabled:
            lines.append(f"{prefix}image 提示词 - 生成图片")
        if "web-search" in enabled:
            lines.append(f"{prefix}search 问题 - 联网搜索后回答")
        if "dice" in enabled:
            lines.append(f"{prefix}dice 或 {prefix}dice 2d6 - 掷骰子")
        if "guess" in enabled:
            lines.append(f"{prefix}guess start/数字/stop - 猜数字")
        if "memory" in enabled:
            lines.append(f"{prefix}remember 内容 - 记录待审核记忆")
            lines.append(f"{prefix}forget 记忆ID - 删除自己的记忆")
        if "admin-lite" in enabled:
            lines.append(f"{prefix}warn @用户 原因 - 管理员警告")
            lines.append(f"{prefix}mute @用户 秒数 原因 - 临时禁言")
            lines.append(f"{prefix}unmute @用户 原因 - 解除禁言")
            lines.append(f"{prefix}banword add/remove/list - 关键词拦截")
        text = "\n".join(lines)
        return SkillResult(text=text, skill_name="help")

    async def ping(self, args: str, ctx: SkillContext) -> SkillResult:
        return SkillResult(text="pong", skill_name="ping")

    async def ai(self, args: str, ctx: SkillContext) -> SkillResult:
        if not args.strip():
            return SkillResult(text=f"用法：{ctx.command_prefix}ai 你的问题", skill_name="ai")
        prompt = args.strip()
        if ctx.recent_context:
            prompt = "最近群聊上下文：\n" + "\n".join(ctx.recent_context[-10:]) + f"\n\n当前问题：{prompt}"
        prompt, skill_name = await self._maybe_add_web_search(
            ctx,
            prompt,
            original_query=args.strip(),
            skill_name="ai",
        )
        result = await ctx.llm.chat(
            ctx.repo,
            prompt,
            group_id=ctx.group_id,
            user_id=ctx.user_id,
            skill_name=skill_name,
        )
        return SkillResult(text=result.text, skill_name="ai", llm_model=result.model)

    async def kb(self, args: str, ctx: SkillContext) -> SkillResult:
        query = args.strip()
        if not query:
            return SkillResult(text=f"用法：{ctx.command_prefix}kb 你的问题", skill_name="kb")
        results = await ctx.repo.search_knowledge(group_id=ctx.group_id, query=query, limit=5)
        if not results:
            return SkillResult(text="知识库里没有找到相关资料。", skill_name="kb")
        context_lines = []
        for index, item in enumerate(results[:5], start=1):
            snippet = item.content
            if len(snippet) > 900:
                snippet = snippet[:900].rstrip() + "..."
            context_lines.append(f"[{index}] Source: {item.source}\n{snippet}")
        prompt = "\n\n".join(
            [
                "User question:",
                query,
                "Knowledge snippets:",
                "\n\n".join(context_lines),
                (
                    "Answer in Chinese. Use only the knowledge snippets. If the snippets are "
                    "insufficient, say the knowledge base does not contain enough information. "
                    "Include source names briefly."
                ),
            ]
        )
        llm_config = await ctx.repo.get_llm_config()
        if llm_config.api_key:
            result = await ctx.llm.complete(
                ctx.repo,
                prompt,
                system_prompt="You answer QQ group knowledge-base questions strictly from provided snippets.",
                group_id=ctx.group_id,
                user_id=ctx.user_id,
                skill_name="kb_answer",
            )
            if result.status == "success" and result.text.strip():
                return SkillResult(text=result.text.strip(), skill_name="kb", llm_model=result.model)
        lines = ["知识库结果："]
        for index, item in enumerate(results, start=1):
            snippet = item.content
            if len(snippet) > 220:
                snippet = snippet[:220].rstrip() + "..."
            lines.append(f"{index}. [{item.source}] {snippet}")
        return SkillResult(text="\n".join(lines), skill_name="kb")

    async def image_generate(self, args: str, ctx: SkillContext) -> SkillResult:
        prompt = args.strip()
        if not prompt:
            return SkillResult(text=f"用法：{ctx.command_prefix}image 图片提示词", skill_name="image")
        if len(prompt) > 1000:
            return SkillResult(text="图片提示词太长，请控制在 1000 字以内。", skill_name="image")
        config = await ctx.repo.get_image_config()
        result = await self.image.generate(config, prompt)
        return SkillResult(text=result.message, skill_name="image", llm_model=result.model)

    async def web_search_answer(self, args: str, ctx: SkillContext) -> SkillResult:
        query = args.strip()
        if not query:
            return SkillResult(
                text=f"Usage: {ctx.command_prefix}search query",
                skill_name="web-search",
            )
        service = ctx.web_search or self.web_search
        config = await ctx.repo.get_web_search_config()
        if not config.enabled:
            return SkillResult(
                text="\u8054\u7f51\u641c\u7d22\u672a\u542f\u7528\uff0c\u8bf7\u5148\u5728\u540e\u53f0\u914d\u7f6e\u3002",
                skill_name="web-search",
            )
        try:
            results = await service.search(config, query)
        except Exception as exc:
            return SkillResult(
                text=f"\u8054\u7f51\u641c\u7d22\u5931\u8d25\uff1a{str(exc)[:120]}",
                skill_name="web-search",
            )
        if not results:
            return SkillResult(
                text="\u6ca1\u6709\u641c\u5230\u53ef\u7528\u7ed3\u679c\u3002",
                skill_name="web-search",
            )

        llm_config = await ctx.repo.get_llm_config()
        if llm_config.api_key:
            result = await ctx.llm.complete(
                ctx.repo,
                with_search_context(query, results),
                system_prompt=(
                    "Answer in Chinese using the provided web search results. "
                    "Be concise and include source links when useful."
                ),
                group_id=ctx.group_id,
                user_id=ctx.user_id,
                skill_name="web_search_answer",
            )
            if result.status == "success" and result.text.strip():
                return SkillResult(
                    text=result.text.strip(),
                    skill_name="web-search",
                    llm_model=result.model,
                )

        return SkillResult(
            text="\u8054\u7f51\u641c\u7d22\u7ed3\u679c\uff1a\n" + format_search_context(results),
            skill_name="web-search",
        )

    async def _maybe_add_web_search(
        self,
        ctx: SkillContext,
        prompt: str,
        *,
        original_query: str,
        skill_name: str,
    ) -> tuple[str, str]:
        if ctx.enabled_skills is not None and "web-search" not in ctx.enabled_skills:
            return prompt, skill_name
        if not should_auto_web_search(original_query):
            return prompt, skill_name
        config = await ctx.repo.get_web_search_config()
        if not config.enabled or not config.auto_enabled:
            return prompt, skill_name
        service = ctx.web_search or self.web_search
        try:
            results = await service.search(config, original_query)
        except Exception:
            return prompt, skill_name
        if not results:
            return prompt, skill_name
        return with_search_context(prompt, results), f"{skill_name}_web_search"

    async def dice(self, args: str, ctx: SkillContext) -> SkillResult:
        spec = args.strip().lower() or "1d6"
        match = re.fullmatch(r"(\d{1,2})d(\d{1,4})", spec)
        if not match:
            return SkillResult(
                text=f"用法：{ctx.command_prefix}dice 或 {ctx.command_prefix}dice 2d6",
                skill_name="dice",
            )
        count = min(max(int(match.group(1)), 1), 20)
        sides = min(max(int(match.group(2)), 2), 1000)
        rolls = [random.randint(1, sides) for _ in range(count)]
        return SkillResult(text=f"{count}d{sides}: {rolls}，总和 {sum(rolls)}", skill_name="dice")

    async def guess(self, args: str, ctx: SkillContext) -> SkillResult:
        command = args.strip().lower()
        if command == "start":
            secret = random.randint(1, 100)
            try:
                await ctx.repo.create_guess_game(
                    group_id=ctx.group_id,
                    user_id=ctx.user_id,
                    secret=secret,
                )
            except ValueError:
                return SkillResult(text="本群已经有进行中的猜数字游戏。", skill_name="guess")
            await ctx.repo.audit(
                action="guess_start",
                actor_user_id=ctx.user_id,
                group_id=ctx.group_id,
                target_type="game",
                target_id="guess",
            )
            return SkillResult(text="猜数字开始：我已经想好 1-100 的数字了。", skill_name="guess")

        if command == "stop":
            game = await ctx.repo.active_game(group_id=ctx.group_id, game_name="guess")
            if game is None:
                return SkillResult(text="本群没有进行中的猜数字游戏。", skill_name="guess")
            user = await ctx.repo.ensure_user(ctx.user_id)
            if game.started_by != ctx.user_id and user.role not in {"super_admin", "group_admin"}:
                return SkillResult(text="权限不足：只有发起者或管理员可以结束游戏。", skill_name="guess")
            await ctx.repo.stop_active_game(group_id=ctx.group_id, game_name="guess")
            await ctx.repo.audit(
                action="guess_stop",
                actor_user_id=ctx.user_id,
                actor_role=user.role,
                group_id=ctx.group_id,
                target_type="game",
                target_id="guess",
            )
            return SkillResult(text="猜数字游戏已结束。", skill_name="guess")

        if not command or not command.isdigit():
            return SkillResult(
                text=f"用法：{ctx.command_prefix}guess start，{ctx.command_prefix}guess 50，{ctx.command_prefix}guess stop",
                skill_name="guess",
            )

        game = await ctx.repo.active_game(group_id=ctx.group_id, game_name="guess")
        if game is None:
            return SkillResult(text=f"本群没有进行中的猜数字游戏，发送 {ctx.command_prefix}guess start 开始。", skill_name="guess")

        guess_number = int(command)
        if guess_number < 1 or guess_number > 100:
            return SkillResult(text="请输入 1-100 之间的数字。", skill_name="guess")

        state = json.loads(game.state_json or "{}")
        secret = int(state.get("secret") or 0)
        attempts = int(state.get("attempts") or 0) + 1
        state["attempts"] = attempts
        if guess_number == secret:
            await ctx.repo.update_game_state(
                game,
                state=state,
                status="won",
                winner_user_id=ctx.user_id,
            )
            await ctx.repo.audit(
                action="guess_win",
                actor_user_id=ctx.user_id,
                group_id=ctx.group_id,
                target_type="game",
                target_id="guess",
                detail={"attempts": attempts},
            )
            return SkillResult(text=f"猜对了，答案是 {secret}。共猜了 {attempts} 次。", skill_name="guess")

        await ctx.repo.update_game_state(game, state=state)
        hint = "大了" if guess_number > secret else "小了"
        return SkillResult(text=f"{guess_number} {hint}，再试一次。", skill_name="guess")

    async def remember(self, args: str, ctx: SkillContext) -> SkillResult:
        content = args.strip()
        if not content:
            return SkillResult(text=f"用法：{ctx.command_prefix}remember 要记住的内容", skill_name="memory")
        if len(content) > 1000:
            return SkillResult(text="记忆内容太长，请控制在 1000 字以内。", skill_name="memory")
        memory = await ctx.repo.create_memory(
            group_id=ctx.group_id,
            user_id=ctx.user_id,
            content=content,
            source="user_command",
            confidence=0.7,
            status="pending",
            created_by=ctx.user_id,
        )
        await ctx.repo.audit(
            action="memory_create_pending",
            actor_user_id=ctx.user_id,
            group_id=ctx.group_id,
            target_type="memory",
            target_id=str(memory.id),
            detail={"source": "user_command"},
        )
        return SkillResult(text=f"已记录为待审核记忆，ID：{memory.id}", skill_name="memory")

    async def forget(self, args: str, ctx: SkillContext) -> SkillResult:
        memory_id_text = args.strip()
        if not memory_id_text or not memory_id_text.isdigit():
            return SkillResult(text=f"用法：{ctx.command_prefix}forget 记忆ID", skill_name="memory")
        memory = await ctx.repo.get_memory_by_id(int(memory_id_text))
        if memory is None or memory.status == "deleted":
            return SkillResult(text="没有找到这条记忆。", skill_name="memory")

        user = await ctx.repo.ensure_user(ctx.user_id)
        can_delete = memory.user_id == ctx.user_id or user.role in {"super_admin", "group_admin"}
        if not can_delete:
            return SkillResult(text="权限不足：只能删除自己的记忆，管理员可以删除本群记忆。", skill_name="memory")
        if user.role == "group_admin" and memory.group_id not in {"", ctx.group_id}:
            return SkillResult(text="权限不足：不能删除其他群的记忆。", skill_name="memory")

        await ctx.repo.update_memory_by_id(memory.id, {"status": "deleted"})
        await ctx.repo.audit(
            action="memory_delete",
            actor_user_id=ctx.user_id,
            actor_role=user.role,
            group_id=ctx.group_id,
            target_type="memory",
            target_id=str(memory.id),
            detail={"source": "user_command"},
        )
        return SkillResult(text=f"已删除记忆，ID：{memory.id}", skill_name="memory")

    async def warn(self, args: str, ctx: SkillContext) -> SkillResult:
        user = await ctx.repo.ensure_user(ctx.user_id)
        if user.role not in {"super_admin", "group_admin"}:
            return SkillResult(text="权限不足：只有管理员可以执行警告。", skill_name="admin-lite")
        if not args.strip():
            return SkillResult(
                text=f"用法：{ctx.command_prefix}warn @用户 原因", skill_name="admin-lite"
            )
        target_id, reason = self._parse_target_user(args)
        group = await ctx.repo.ensure_group(ctx.group_id)
        moderation = ctx.repo.group_moderation_config(group)
        violation_count = 0
        if target_id:
            since = now_utc() - timedelta(hours=moderation.violation_window_hours)
            violation_count = (
                await ctx.repo.moderation_violation_count(
                    group_id=ctx.group_id,
                    user_id=target_id,
                    since=since,
                )
                + 1
            )
        await ctx.repo.audit(
            action="warn",
            actor_user_id=ctx.user_id,
            actor_role=user.role,
            group_id=ctx.group_id,
            target_type="user" if target_id else "",
            target_id=target_id,
            detail={
                "args": args.strip(),
                "reason": reason or args.strip(),
                "violation_count": violation_count,
                "window_hours": moderation.violation_window_hours,
            },
        )
        suffix = f"，近期累计违规 {violation_count} 次" if target_id else ""
        return SkillResult(text=f"已记录警告：{args.strip()}{suffix}", skill_name="admin-lite")

    async def mute(self, args: str, ctx: SkillContext) -> SkillResult:
        user = await ctx.repo.ensure_user(ctx.user_id)
        if user.role not in {"super_admin", "group_admin"}:
            return SkillResult(text="权限不足：只有管理员可以执行禁言。", skill_name="admin-lite")
        target_id, rest = self._parse_target_user(args)
        if not target_id:
            return SkillResult(
                text=f"用法：{ctx.command_prefix}mute @用户 秒数 原因", skill_name="admin-lite"
            )
        parts = rest.split(maxsplit=1)
        if not parts or not parts[0].isdigit():
            return SkillResult(text="请提供禁言秒数。", skill_name="admin-lite")
        duration = max(10, min(int(parts[0]), 3600))
        reason = parts[1].strip() if len(parts) > 1 else "manual_mute"
        if ctx.sender is not None and hasattr(ctx.sender, "mute_user"):
            await ctx.sender.mute_user(ctx.group_id, target_id, duration)
        await ctx.repo.audit(
            action="mute",
            actor_user_id=ctx.user_id,
            actor_role=user.role,
            group_id=ctx.group_id,
            target_type="user",
            target_id=target_id,
            detail={"duration": duration, "reason": reason},
        )
        return SkillResult(text=f"已临时禁言 {target_id} {duration} 秒。", skill_name="admin-lite")

    async def unmute(self, args: str, ctx: SkillContext) -> SkillResult:
        user = await ctx.repo.ensure_user(ctx.user_id)
        if user.role not in {"super_admin", "group_admin"}:
            return SkillResult(text="权限不足：只有管理员可以解除禁言。", skill_name="admin-lite")
        target_id, rest = self._parse_target_user(args)
        if not target_id:
            return SkillResult(
                text=f"用法：{ctx.command_prefix}unmute @用户 原因", skill_name="admin-lite"
            )
        reason = rest.strip() or "manual_unmute"
        if ctx.sender is not None and hasattr(ctx.sender, "mute_user"):
            await ctx.sender.mute_user(ctx.group_id, target_id, 0)
        await ctx.repo.audit(
            action="unmute",
            actor_user_id=ctx.user_id,
            actor_role=user.role,
            group_id=ctx.group_id,
            target_type="user",
            target_id=target_id,
            detail={"reason": reason},
        )
        return SkillResult(text=f"已解除 {target_id} 的禁言。", skill_name="admin-lite")

    async def banword(self, args: str, ctx: SkillContext) -> SkillResult:
        user = await ctx.repo.ensure_user(ctx.user_id)
        if user.role not in {"super_admin", "group_admin"}:
            return SkillResult(text="权限不足：只有管理员可以管理关键词。", skill_name="admin-lite")

        parts = args.split(maxsplit=2)
        if not parts:
            return SkillResult(
                text=(
                    f"用法：{ctx.command_prefix}banword add 关键词 [回复]，"
                    f"{ctx.command_prefix}banword remove 关键词，"
                    f"{ctx.command_prefix}banword list"
                ),
                skill_name="admin-lite",
            )

        action = parts[0].lower()
        if action == "list":
            rules = await ctx.repo.list_keyword_rules(ctx.group_id)
            if not rules:
                return SkillResult(text="当前没有启用的关键词规则。", skill_name="admin-lite")
            return SkillResult(
                text="关键词规则：\n" + "\n".join(f"- {rule.keyword}" for rule in rules),
                skill_name="admin-lite",
            )
        if len(parts) < 2:
            return SkillResult(text="请提供关键词。", skill_name="admin-lite")
        keyword = parts[1].strip()
        if action == "add":
            response = parts[2].strip() if len(parts) >= 3 else "命中关键词，已记录。"
            await ctx.repo.add_keyword_rule(
                group_id=ctx.group_id,
                keyword=keyword,
                response=response,
                created_by=ctx.user_id,
            )
            await ctx.repo.audit(
                action="banword_add",
                actor_user_id=ctx.user_id,
                actor_role=user.role,
                group_id=ctx.group_id,
                target_type="keyword",
                target_id=keyword,
            )
            return SkillResult(text=f"已添加关键词：{keyword}", skill_name="admin-lite")
        if action == "remove":
            count = await ctx.repo.delete_keyword_rule(group_id=ctx.group_id, keyword=keyword)
            await ctx.repo.audit(
                action="banword_remove",
                actor_user_id=ctx.user_id,
                actor_role=user.role,
                group_id=ctx.group_id,
                target_type="keyword",
                target_id=keyword,
            )
            return SkillResult(text=f"已删除 {count} 条关键词规则。", skill_name="admin-lite")
        return SkillResult(
            text=f"用法：{ctx.command_prefix}banword add/remove/list", skill_name="admin-lite"
        )

    @staticmethod
    def _parse_target_user(args: str) -> tuple[str, str]:
        stripped = args.strip()
        if not stripped:
            return "", ""
        at_match = re.match(r"\[CQ:at,qq=(\d+)\]\s*(.*)", stripped)
        if at_match:
            return at_match.group(1), at_match.group(2).strip()
        target, _, rest = stripped.partition(" ")
        if target.isdigit():
            return target, rest.strip()
        return "", stripped
