from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.cache import BotCache
from app.llm import LLMService
from app.models import ScheduledTask, now_utc
from app.repository import Repository


def task_payload(task: ScheduledTask) -> dict[str, Any]:
    try:
        payload = json.loads(task.payload_json or "{}")
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


async def run_due_tasks_once(
    repo: Repository,
    sender: Any,
    cache: BotCache | None,
    llm: LLMService | None = None,
) -> int:
    now = now_utc()
    tasks = await repo.due_scheduled_tasks(now)
    executed = 0
    for task in tasks:
        started_at = now_utc()
        try:
            result_message = await execute_task(repo, sender, cache, task, llm=llm)
            mark_task_success(task)
            await repo.create_task_run(
                task_id=task.id,
                task_type=task.task_type,
                group_id=task.group_id,
                status="success",
                result_message=result_message,
                started_at=started_at,
                finished_at=now_utc(),
            )
            executed += 1
        except Exception as exc:
            await repo.create_task_run(
                task_id=task.id,
                task_type=task.task_type,
                group_id=task.group_id,
                status="failed",
                error_message=str(exc),
                started_at=started_at,
                finished_at=now_utc(),
            )
            task.last_run_at = now_utc()
            advance_next_run(task)
    return executed


async def execute_task(
    repo: Repository,
    sender: Any,
    cache: BotCache | None,
    task: ScheduledTask,
    *,
    llm: LLMService | None = None,
) -> str:
    payload = task_payload(task)
    if task.task_type == "reminder_once":
        message = str(payload.get("message") or "").strip()
        if not message:
            raise ValueError("reminder message is required")
        if not task.group_id:
            raise ValueError("group_id is required for group reminder")
        await ensure_group_enabled(repo, task.group_id)
        await sender.send_group_message(task.group_id, message)
        return "reminder_sent"
    if task.task_type == "daily_summary":
        if not task.group_id:
            raise ValueError("group_id is required for daily summary")
        await ensure_group_enabled(repo, task.group_id)
        summary = await build_daily_summary(repo, task.group_id, int(payload.get("hours") or 24))
        await sender.send_group_message(task.group_id, summary)
        return "daily_summary_sent"
    if task.task_type == "cleanup_context":
        if cache is not None and hasattr(cache, "clear_contexts"):
            await cache.clear_contexts()
        expired_games = await repo.expire_game_states()
        return f"context_cleanup_done;expired_games={expired_games}"
    if task.task_type == "memory_summarize":
        if not task.group_id:
            raise ValueError("group_id is required for memory summary")
        await ensure_group_enabled(repo, task.group_id)
        hours = max(1, min(int(payload.get("hours") or 24), 168))
        limit = max(5, min(int(payload.get("limit") or 50), 200))
        content = await build_memory_candidate(repo, llm, task.group_id, hours, limit)
        if not content:
            return "memory_summary_skipped;messages=0"
        memory = await repo.create_memory(
            group_id=task.group_id,
            user_id="",
            content=content[:2000],
            source="scheduled_chat_summary",
            confidence=0.6,
            status="pending",
            created_by="scheduler",
        )
        await repo.audit(
            action="memory_summary_create_pending",
            group_id=task.group_id,
            target_type="memory",
            target_id=str(memory.id),
            detail={"source": "scheduler", "task_id": task.id, "hours": hours, "limit": limit},
        )
        return f"memory_summary_pending;memory_id={memory.id}"
    if task.task_type == "knowledge_reindex":
        only_failed = bool(payload.get("only_failed", False))
        include_disabled = bool(payload.get("include_disabled", False))
        limit = max(1, min(int(payload.get("limit") or 100), 500))
        documents = await repo.list_knowledge_documents(
            group_id=task.group_id or None,
            index_status="failed" if only_failed else None,
        )
        selected = [
            document
            for document in documents
            if include_disabled or document.enabled
        ][:limit]
        for document in selected:
            await repo.rebuild_knowledge_chunks(document)
        succeeded = sum(
            1 for document in selected if document.index_status in {"completed", "vectorized"}
        )
        failed = sum(1 for document in selected if document.index_status == "failed")
        skipped = max(0, len(documents) - len(selected))
        await repo.audit(
            action="knowledge_docs_reindex",
            group_id=task.group_id,
            target_type="knowledge_doc",
            target_id="bulk",
            detail={
                "source": "scheduler",
                "task_id": task.id,
                "only_failed": only_failed,
                "include_disabled": include_disabled,
                "requested": len(documents),
                "processed": len(selected),
                "succeeded": succeeded,
                "failed": failed,
                "skipped": skipped,
            },
            result="failed" if failed else "success",
        )
        return (
            "knowledge_reindex_done;"
            f"processed={len(selected)};succeeded={succeeded};failed={failed};skipped={skipped}"
        )
    raise ValueError(f"unsupported task_type: {task.task_type}")


async def ensure_group_enabled(repo: Repository, group_id: str) -> None:
    bot_settings = await repo.get_bot_settings()
    allowed_groups = bot_settings.allowed_group_set
    if allowed_groups and group_id not in allowed_groups:
        raise ValueError("target group is not allowed")
    group = await repo.ensure_group(group_id)
    if not group.enabled:
        raise ValueError("target group is disabled")


async def build_daily_summary(repo: Repository, group_id: str, hours: int) -> str:
    since = now_utc() - timedelta(hours=max(1, min(hours, 168)))
    messages = await repo.recent_group_messages(group_id, since, limit=20)
    if not messages:
        return "今日群聊总结：\n消息数：0\n暂无可总结内容。"

    sample_lines = []
    for message in messages[-5:]:
        content = message.content.strip().replace("\n", " ")
        if len(content) > 80:
            content = content[:80].rstrip() + "..."
        sample_lines.append(f"- {message.user_id}: {content}")
    return "\n".join(
        [
            "今日群聊总结：",
            f"消息数：{len(messages)}",
            "最近片段：",
            *sample_lines,
        ]
    )


async def build_memory_candidate(
    repo: Repository,
    llm: LLMService | None,
    group_id: str,
    hours: int,
    limit: int,
) -> str:
    since = now_utc() - timedelta(hours=hours)
    messages = await repo.recent_group_messages(group_id, since, limit=limit)
    if not messages:
        return ""
    sample_lines = []
    for message in messages:
        content = message.content.strip().replace("\n", " ")
        if not content:
            continue
        if len(content) > 180:
            content = content[:180].rstrip() + "..."
        sample_lines.append(f"{message.user_id}: {content}")
    if not sample_lines:
        return ""

    config = await repo.get_llm_config()
    if llm is not None and config.api_key:
        prompt = "\n".join(
            [
                "请把下面 QQ 群聊天整理成一条待审核的长期记忆候选。",
                "要求：只总结稳定偏好、群内规则、长期项目事实或反复出现的重要信息。",
                "不要记录临时闲聊、一次性情绪、隐私密钥、密码、联系方式或不确定事实。",
                "输出 1 到 5 条短句，用分号分隔，不要解释。",
                "",
                "群聊片段：",
                *sample_lines,
            ]
        )
        result = await llm.chat(
            repo,
            prompt,
            group_id=group_id,
            user_id="",
            skill_name="memory_summary",
        )
        text = result.text.strip()
        if text:
            return text[:2000]

    return "\n".join(
        [
            f"群 {group_id} 最近 {hours} 小时聊天摘要候选：",
            *sample_lines[-10:],
        ]
    )[:2000]


async def build_memory_candidate_from_messages(
    repo: Repository,
    llm: LLMService | None,
    group_id: str,
    messages: list,
    *,
    source_hint: str,
) -> str:
    sample_lines = []
    for message in messages:
        content = message.content.strip().replace("\n", " ")
        if not content:
            continue
        if len(content) > 180:
            content = content[:180].rstrip() + "..."
        sample_lines.append(f"{message.user_id}: {content}")
    if not sample_lines:
        return ""

    config = await repo.get_llm_config()
    if llm is not None and config.api_key:
        prompt = "\n".join(
            [
                "请把下面 QQ 群聊天整理成待审核的长期记忆候选。",
                "只总结稳定偏好、群内规则、长期项目事实或反复出现的重要信息。",
                "不要记录临时闲聊、一次性情绪、隐私密钥、密码、联系方式或不确定事实。",
                "输出 1 到 5 条短句，用分号分隔，不要解释。",
                "",
                f"范围：{source_hint}",
                "群聊片段：",
                *sample_lines,
            ]
        )
        result = await llm.chat(
            repo,
            prompt,
            group_id=group_id,
            user_id="",
            skill_name="memory_summary",
        )
        text = result.text.strip()
        if text:
            return text[:2000]

    return "\n".join(
        [
            f"群 {group_id} {source_hint}聊天摘要候选：",
            *sample_lines[-10:],
        ]
    )[:2000]


async def maybe_create_memory_summary_by_count(
    repo: Repository,
    llm: LLMService | None,
    group_id: str,
    threshold: int,
) -> int | None:
    threshold = max(10, min(threshold, 5000))
    last_message_id = await repo.memory_summary_last_message_id(group_id)
    count = await repo.count_group_messages_after_id(group_id, last_message_id)
    if count < threshold:
        return None

    messages = await repo.group_messages_after_id(group_id, last_message_id, limit=threshold)
    if len(messages) < threshold:
        return None
    content = await build_memory_candidate_from_messages(
        repo,
        llm,
        group_id,
        messages,
        source_hint=f"累计 {len(messages)} 条",
    )
    await repo.set_memory_summary_last_message_id(group_id, messages[-1].id)
    if not content:
        return None
    memory = await repo.create_memory(
        group_id=group_id,
        user_id="",
        content=content[:2000],
        source="auto_chat_count_summary",
        confidence=0.6,
        status="pending",
        created_by="message_count",
    )
    await repo.audit(
        action="memory_summary_create_pending",
        group_id=group_id,
        target_type="memory",
        target_id=str(memory.id),
        detail={
            "source": "message_count",
            "threshold": threshold,
            "message_count": len(messages),
            "last_message_id": messages[-1].id,
        },
    )
    return memory.id


def mark_task_success(task: ScheduledTask) -> None:
    task.last_run_at = now_utc()
    advance_next_run(task)


def advance_next_run(task: ScheduledTask) -> None:
    if task.schedule_type == "once":
        task.enabled = False
        task.next_run_at = None
    elif task.schedule_type == "daily":
        next_run_at = (task.next_run_at or now_utc()) + timedelta(days=1)
        while next_run_at <= now_utc():
            next_run_at += timedelta(days=1)
        task.next_run_at = next_run_at
    elif task.schedule_type == "interval":
        seconds = max(task.interval_seconds, 60)
        task.next_run_at = now_utc() + timedelta(seconds=seconds)


class TaskScheduler:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker,
        settings,
        sender: Any,
        cache: BotCache | None,
        llm: LLMService | None = None,
        interval_seconds: float = 30,
    ):
        self.session_factory = session_factory
        self.settings = settings
        self.sender = sender
        self.cache = cache
        self.llm = llm
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while not self._stop.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue

    async def run_once(self) -> int:
        async with self.session_factory() as session:
            repo = Repository(session, self.settings)
            try:
                executed = await run_due_tasks_once(repo, self.sender, self.cache, llm=self.llm)
                await session.commit()
                return executed
            except Exception:
                await session.rollback()
                raise
