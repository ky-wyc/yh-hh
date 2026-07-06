from __future__ import annotations

import json
from datetime import timedelta

from app.config import Settings
from app.models import now_utc
from app.repository import Repository
from app.scheduler import run_due_tasks_once


async def test_due_one_time_reminder_sends_message_and_records_history(repo, sender):
    task = await repo.create_scheduled_task(
        name="测试提醒",
        task_type="reminder_once",
        schedule_type="once",
        group_id="10001",
        payload={"message": "记得测试"},
        next_run_at=now_utc() - timedelta(seconds=1),
        enabled=True,
        created_by="admin",
    )

    executed = await run_due_tasks_once(repo, sender, cache=None)
    runs = await repo.list_task_runs()
    refreshed = await repo.get_scheduled_task_by_id(task.id)

    assert executed == 1
    assert sender.group_messages == [("10001", "记得测试")]
    assert runs[0].status == "success"
    assert runs[0].task_id == task.id
    assert refreshed is not None
    assert refreshed.enabled is False
    assert refreshed.next_run_at is None


async def test_daily_summary_summarizes_recent_group_messages(repo, sender):
    await repo.save_message(
        group_id="10001",
        user_id="20001",
        message_id="m1",
        dedup_key="m1",
        content="今天讨论部署",
        raw_event={},
    )
    await repo.save_message(
        group_id="10001",
        user_id="20002",
        message_id="m2",
        dedup_key="m2",
        content="明天继续测试",
        raw_event={},
    )
    await repo.create_scheduled_task(
        name="每日总结",
        task_type="daily_summary",
        schedule_type="daily",
        group_id="10001",
        payload={"hours": 24},
        next_run_at=now_utc() - timedelta(seconds=1),
        enabled=True,
        created_by="admin",
    )

    executed = await run_due_tasks_once(repo, sender, cache=None)

    assert executed == 1
    assert sender.group_messages
    summary = sender.group_messages[0][1]
    assert "今日群聊总结" in summary
    assert "消息数：2" in summary
    assert "今天讨论部署" in summary


async def test_memory_summary_task_creates_pending_memory(repo, sender):
    await repo.save_message(
        group_id="10001",
        user_id="20001",
        message_id="mem1",
        dedup_key="mem1",
        content="Please remember that this group prefers concise deployment answers.",
        raw_event={},
    )
    await repo.save_message(
        group_id="10001",
        user_id="20002",
        message_id="mem2",
        dedup_key="mem2",
        content="We usually discuss the QQBot rollout in this group.",
        raw_event={},
    )
    await repo.create_scheduled_task(
        name="chat memory summary",
        task_type="memory_summarize",
        schedule_type="interval",
        group_id="10001",
        payload={"hours": 24, "limit": 20},
        next_run_at=now_utc() - timedelta(seconds=1),
        interval_seconds=3600,
        enabled=True,
        created_by="admin",
    )

    executed = await run_due_tasks_once(repo, sender, cache=None)

    memories = await repo.list_memories_for_admin(status="pending", group_id="10001")
    runs = await repo.list_task_runs()
    assert executed == 1
    assert len(memories) == 1
    assert memories[0].source == "scheduled_chat_summary"
    assert memories[0].status == "pending"
    assert "QQBot rollout" in memories[0].content
    assert "memory_summary_pending" in runs[0].result_message


async def test_group_task_does_not_send_when_group_is_disabled(repo, sender):
    await repo.update_group("10001", enabled=False)
    await repo.create_scheduled_task(
        name="停用群提醒",
        task_type="reminder_once",
        schedule_type="once",
        group_id="10001",
        payload={"message": "不应该发出"},
        next_run_at=now_utc() - timedelta(seconds=1),
        enabled=True,
        created_by="admin",
    )

    executed = await run_due_tasks_once(repo, sender, cache=None)
    runs = await repo.list_task_runs()

    assert executed == 0
    assert sender.group_messages == []
    assert runs[0].status == "failed"
    assert "disabled" in runs[0].error_message


async def test_group_task_respects_allowed_groups(session_factory, sender):
    async with session_factory() as session:
        restricted_repo = Repository(session, Settings(REDIS_URL="", ALLOWED_GROUPS="20002"))
        await restricted_repo.create_scheduled_task(
            name="未授权群提醒",
            task_type="reminder_once",
            schedule_type="once",
            group_id="10001",
            payload={"message": "不应该发出"},
            next_run_at=now_utc() - timedelta(seconds=1),
            enabled=True,
            created_by="admin",
        )

        executed = await run_due_tasks_once(restricted_repo, sender, cache=None)
        runs = await restricted_repo.list_task_runs()

    assert executed == 0
    assert sender.group_messages == []
    assert runs[0].status == "failed"
    assert "not allowed" in runs[0].error_message


async def test_cleanup_context_task_expires_game_states(repo, sender):
    await repo.create_guess_game(
        group_id="10001",
        user_id="20001",
        secret=42,
        expires_in_hours=-1,
    )
    await repo.create_scheduled_task(
        name="清理上下文",
        task_type="cleanup_context",
        schedule_type="once",
        payload={},
        next_run_at=now_utc() - timedelta(seconds=1),
        enabled=True,
        created_by="admin",
    )

    executed = await run_due_tasks_once(repo, sender, cache=None)
    runs = await repo.list_task_runs()
    active_game = await repo.active_game(group_id="10001", game_name="guess")

    assert executed == 1
    assert active_game is None
    assert runs[0].status == "success"
    assert "expired_games=1" in runs[0].result_message


async def test_knowledge_reindex_task_rebuilds_documents_and_records_history(repo, sender):
    first = await repo.create_knowledge_document(
        group_id="10001",
        title="FAQ 1",
        content="第一篇知识。",
        enabled=True,
        created_by="admin",
    )
    second = await repo.create_knowledge_document(
        group_id="10001",
        title="FAQ 2",
        content="第二篇知识。",
        enabled=True,
        created_by="admin",
    )
    await repo.create_scheduled_task(
        name="知识库后台重建",
        task_type="knowledge_reindex",
        schedule_type="once",
        group_id="10001",
        payload={"only_failed": False, "include_disabled": False, "limit": 10},
        next_run_at=now_utc() - timedelta(seconds=1),
        enabled=True,
        created_by="admin",
    )

    executed = await run_due_tasks_once(repo, sender, cache=None)
    runs = await repo.list_task_runs()
    history = await repo.list_knowledge_reindex_runs(group_id="10001")
    detail = json.loads(history[0].detail_json)

    assert executed == 1
    assert sender.group_messages == []
    assert runs[0].status == "success"
    assert "knowledge_reindex_done" in runs[0].result_message
    assert detail["source"] == "scheduler"
    assert detail["processed"] == 2
    assert detail["succeeded"] == 2
    assert detail["requested"] == 2
    assert {document.id for document in await repo.list_knowledge_documents(group_id="10001")} == {
        first.id,
        second.id,
    }
