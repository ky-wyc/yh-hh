from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.cache import BotCache
from app.models import ScheduledTask, now_utc
from app.repository import Repository


def task_payload(task: ScheduledTask) -> dict[str, Any]:
    try:
        payload = json.loads(task.payload_json or "{}")
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


async def run_due_tasks_once(repo: Repository, sender: Any, cache: BotCache | None) -> int:
    now = now_utc()
    tasks = await repo.due_scheduled_tasks(now)
    executed = 0
    for task in tasks:
        started_at = now_utc()
        try:
            result_message = await execute_task(repo, sender, cache, task)
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
        interval_seconds: float = 30,
    ):
        self.session_factory = session_factory
        self.settings = settings
        self.sender = sender
        self.cache = cache
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
                executed = await run_due_tasks_once(repo, self.sender, self.cache)
                await session.commit()
                return executed
            except Exception:
                await session.rollback()
                raise
