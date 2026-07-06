from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass

from app.llm import LLMService
from app.repository import Repository


SKILL_CATALOG: dict[str, dict[str, str]] = {
    "help": {"display_name": "帮助", "description": "查看机器人可用命令。"},
    "ping": {"display_name": "健康检查", "description": "检查机器人是否在线。"},
    "ai": {"display_name": "AI 问答", "description": "大模型聊天、@ 回复和主动回答。"},
    "kb": {"display_name": "知识库", "description": "查询后台维护的群知识库。"},
    "dice": {"display_name": "掷骰子", "description": "娱乐掷骰子命令。"},
    "guess": {"display_name": "猜数字", "description": "按群持久保存的猜数字游戏。"},
    "memory": {"display_name": "长期记忆", "description": "手动记住和忘记待审核记忆。"},
    "admin-lite": {"display_name": "基础群管", "description": "警告、关键词拦截和轻量群管命令。"},
}

COMMAND_SKILLS: dict[str, str] = {
    "help": "help",
    "ping": "ping",
    "ai": "ai",
    "kb": "kb",
    "dice": "dice",
    "guess": "guess",
    "remember": "memory",
    "forget": "memory",
    "warn": "admin-lite",
    "banword": "admin-lite",
}


@dataclass(slots=True)
class SkillContext:
    repo: Repository
    llm: LLMService
    group_id: str
    user_id: str
    message_id: str = ""
    command_prefix: str = "/"
    recent_context: list[str] | None = None
    enabled_skills: set[str] | None = None


@dataclass(slots=True)
class SkillResult:
    text: str
    skill_name: str
    llm_model: str = ""


class SkillRegistry:
    def __init__(self):
        self._handlers = {
            "help": self.help,
            "ping": self.ping,
            "ai": self.ai,
            "kb": self.kb,
            "dice": self.dice,
            "guess": self.guess,
            "remember": self.remember,
            "forget": self.forget,
            "warn": self.warn,
            "banword": self.banword,
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
        if "dice" in enabled:
            lines.append(f"{prefix}dice 或 {prefix}dice 2d6 - 掷骰子")
        if "guess" in enabled:
            lines.append(f"{prefix}guess start/数字/stop - 猜数字")
        if "memory" in enabled:
            lines.append(f"{prefix}remember 内容 - 记录待审核记忆")
            lines.append(f"{prefix}forget 记忆ID - 删除自己的记忆")
        if "admin-lite" in enabled:
            lines.append(f"{prefix}warn @用户 原因 - 管理员警告")
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
        result = await ctx.llm.chat(
            ctx.repo,
            prompt,
            group_id=ctx.group_id,
            user_id=ctx.user_id,
            skill_name="ai",
        )
        return SkillResult(text=result.text, skill_name="ai", llm_model=result.model)

    async def kb(self, args: str, ctx: SkillContext) -> SkillResult:
        query = args.strip()
        if not query:
            return SkillResult(text=f"用法：{ctx.command_prefix}kb 你的问题", skill_name="kb")
        results = await ctx.repo.search_knowledge(group_id=ctx.group_id, query=query, limit=3)
        if not results:
            return SkillResult(text="知识库里没有找到相关资料。", skill_name="kb")
        lines = ["知识库结果："]
        for index, item in enumerate(results, start=1):
            snippet = item.content
            if len(snippet) > 220:
                snippet = snippet[:220].rstrip() + "..."
            lines.append(f"{index}. [{item.source}] {snippet}")
        return SkillResult(text="\n".join(lines), skill_name="kb")

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
        await ctx.repo.audit(
            action="warn",
            actor_user_id=ctx.user_id,
            actor_role=user.role,
            group_id=ctx.group_id,
            detail={"args": args.strip()},
        )
        return SkillResult(text=f"已记录警告：{args.strip()}", skill_name="admin-lite")

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
