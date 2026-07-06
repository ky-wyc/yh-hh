from __future__ import annotations

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
