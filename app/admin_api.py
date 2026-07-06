from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import login, require_admin
from app.repository import Repository
from app.schemas import (
    BotSettingsOut,
    BotSettingsUpdate,
    GroupUpdate,
    KeywordRuleCreate,
    KeywordRuleOut,
    KeywordRuleUpdate,
    KnowledgeDocumentCreate,
    KnowledgeDocumentOut,
    KnowledgeDocumentUpdate,
    KnowledgeSearchRequest,
    LLMSettingsOut,
    LLMSettingsUpdate,
    LLMTestRequest,
    LoginRequest,
    LoginResponse,
    MemoryCreate,
    MemoryOut,
    MemoryUpdate,
    ScheduledTaskCreate,
    ScheduledTaskOut,
    ScheduledTaskUpdate,
    TaskRunOut,
)

router = APIRouter(prefix="/api")


async def get_session(request: Request) -> AsyncSession:
    session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def repo_from(request: Request, session: AsyncSession) -> Repository:
    return Repository(session, request.app.state.settings)


def keyword_rule_out(rule) -> KeywordRuleOut:
    return KeywordRuleOut(
        id=rule.id,
        group_id=rule.group_id,
        keyword=rule.keyword,
        response=rule.response,
        enabled=rule.enabled,
        created_by=rule.created_by,
        created_at=rule.created_at.isoformat(),
    )


def memory_out(memory) -> MemoryOut:
    return MemoryOut(
        id=memory.id,
        group_id=memory.group_id,
        user_id=memory.user_id,
        content=memory.content,
        source=memory.source,
        confidence=memory.confidence,
        status=memory.status,
        created_by=memory.created_by,
        created_at=memory.created_at.isoformat(),
        updated_at=memory.updated_at.isoformat(),
    )


def knowledge_document_out(document) -> KnowledgeDocumentOut:
    return KnowledgeDocumentOut(
        id=document.id,
        group_id=document.group_id,
        title=document.title,
        content=document.content,
        enabled=document.enabled,
        index_status=document.index_status,
        index_error=document.index_error,
        chunk_count=document.chunk_count,
        created_by=document.created_by,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
    )


def naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def scheduled_task_out(task) -> ScheduledTaskOut:
    try:
        payload = json.loads(task.payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except json.JSONDecodeError:
        payload = {}
    return ScheduledTaskOut(
        id=task.id,
        name=task.name,
        task_type=task.task_type,
        schedule_type=task.schedule_type,
        group_id=task.group_id,
        user_id=task.user_id,
        payload=payload,
        enabled=task.enabled,
        next_run_at=task.next_run_at.isoformat() if task.next_run_at else None,
        interval_seconds=task.interval_seconds,
        last_run_at=task.last_run_at.isoformat() if task.last_run_at else None,
        created_by=task.created_by,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )


def task_run_out(run) -> TaskRunOut:
    return TaskRunOut(
        id=run.id,
        task_id=run.task_id,
        task_type=run.task_type,
        group_id=run.group_id,
        status=run.status,
        result_message=run.result_message,
        error_message=run.error_message,
        started_at=run.started_at.isoformat(),
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
    )


def audit_safe_detail(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: audit_safe_detail(item) for key, item in value.items()}
    if isinstance(value, list):
        return [audit_safe_detail(item) for item in value]
    return value


@router.post("/auth/login", response_model=LoginResponse)
async def auth_login(request: Request, payload: LoginRequest) -> LoginResponse:
    token = login(
        request.app.state.settings,
        request.app.state.token_store,
        payload.username,
        payload.password,
    )
    return LoginResponse(access_token=token)


@router.get("/auth/me", dependencies=[Depends(require_admin)])
async def auth_me() -> dict[str, str]:
    return {"role": "super_admin"}


@router.get("/system/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/system/ready")
async def ready(request: Request, session: AsyncSession = Depends(get_session)):
    await session.execute(text("select 1"))
    cache_status = await request.app.state.rate_limiter.health()
    return {"status": "ok", "database": "ok", "cache": cache_status}


@router.get("/system/onebot-status", dependencies=[Depends(require_admin)])
async def onebot_status(request: Request):
    status = request.app.state.onebot.status
    return {
        "online": status.online,
        "connection_mode": status.connection_mode,
        "connected_at": status.connected_at.isoformat() if status.connected_at else None,
        "disconnected_at": status.disconnected_at.isoformat() if status.disconnected_at else None,
        "last_event_at": status.last_event_at.isoformat() if status.last_event_at else None,
        "last_action_at": status.last_action_at.isoformat() if status.last_action_at else None,
        "last_error": status.last_error,
    }


@router.get("/dashboard/overview", dependencies=[Depends(require_admin)])
async def dashboard_overview(request: Request, session: AsyncSession = Depends(get_session)):
    repo = repo_from(request, session)
    overview = await repo.overview()
    overview["onebot_online"] = request.app.state.onebot.status.online
    return overview


@router.get("/groups", dependencies=[Depends(require_admin)])
async def list_groups(request: Request, session: AsyncSession = Depends(get_session)):
    repo = repo_from(request, session)
    groups = await repo.get_groups()
    return [
        {
            "qq_group_id": group.qq_group_id,
            "name": group.name,
            "enabled": group.enabled,
            "reply_mode": group.reply_mode,
        }
        for group in groups
    ]


@router.patch("/groups/{qq_group_id}", dependencies=[Depends(require_admin)])
async def patch_group(
    qq_group_id: Annotated[str, Path(pattern=r"^\d+$")],
    payload: GroupUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    group = await repo.update_group(
        qq_group_id,
        enabled=payload.enabled,
        reply_mode=payload.reply_mode,
        name=payload.name,
    )
    await repo.audit(action="group_update", target_type="group", target_id=qq_group_id)
    await session.commit()
    return {
        "qq_group_id": group.qq_group_id,
        "name": group.name,
        "enabled": group.enabled,
        "reply_mode": group.reply_mode,
    }


@router.get("/keyword-rules", response_model=list[KeywordRuleOut], dependencies=[Depends(require_admin)])
async def list_keyword_rules(
    request: Request,
    session: AsyncSession = Depends(get_session),
    group_id: str | None = Query(default=None, pattern=r"^\d*$"),
):
    repo = repo_from(request, session)
    rules = await repo.list_keyword_rules_for_admin(group_id=group_id)
    return [keyword_rule_out(rule) for rule in rules]


@router.post("/keyword-rules", response_model=KeywordRuleOut, dependencies=[Depends(require_admin)])
async def create_keyword_rule(
    payload: KeywordRuleCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    rule, created = await repo.create_or_update_keyword_rule(
        group_id=payload.group_id,
        keyword=payload.keyword,
        response=payload.response,
        enabled=payload.enabled,
        created_by="admin",
    )
    await repo.audit(
        action="keyword_rule_create" if created else "keyword_rule_update",
        group_id=rule.group_id,
        target_type="keyword",
        target_id=rule.keyword,
        detail={"source": "admin", "enabled": rule.enabled},
    )
    await session.commit()
    return keyword_rule_out(rule)


@router.patch(
    "/keyword-rules/{rule_id}",
    response_model=KeywordRuleOut,
    dependencies=[Depends(require_admin)],
)
async def update_keyword_rule(
    rule_id: Annotated[int, Path(ge=1)],
    payload: KeywordRuleUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    try:
        rule = await repo.update_keyword_rule_by_id(rule_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if rule is None:
        raise HTTPException(status_code=404, detail="keyword rule not found")
    await repo.audit(
        action="keyword_rule_update",
        group_id=rule.group_id,
        target_type="keyword",
        target_id=rule.keyword,
        detail={"source": "admin", "changes": payload.model_dump(exclude_unset=True)},
    )
    await session.commit()
    return keyword_rule_out(rule)


@router.delete("/keyword-rules/{rule_id}", dependencies=[Depends(require_admin)])
async def delete_keyword_rule(
    rule_id: Annotated[int, Path(ge=1)],
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    rule = await repo.get_keyword_rule_by_id(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="keyword rule not found")
    group_id = rule.group_id
    keyword = rule.keyword
    await repo.delete_keyword_rule_by_id(rule_id)
    await repo.audit(
        action="keyword_rule_delete",
        group_id=group_id,
        target_type="keyword",
        target_id=keyword,
        detail={"source": "admin"},
    )
    await session.commit()
    return {"deleted": True}


@router.get("/scheduled-tasks", response_model=list[ScheduledTaskOut], dependencies=[Depends(require_admin)])
async def list_scheduled_tasks(
    request: Request,
    session: AsyncSession = Depends(get_session),
    group_id: str | None = Query(default=None, pattern=r"^\d*$"),
):
    repo = repo_from(request, session)
    tasks = await repo.list_scheduled_tasks(group_id=group_id)
    return [scheduled_task_out(task) for task in tasks]


@router.post("/scheduled-tasks", response_model=ScheduledTaskOut, dependencies=[Depends(require_admin)])
async def create_scheduled_task(
    payload: ScheduledTaskCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    task = await repo.create_scheduled_task(
        name=payload.name,
        task_type=payload.task_type,
        schedule_type=payload.schedule_type,
        group_id=payload.group_id,
        user_id=payload.user_id,
        payload=payload.payload,
        enabled=payload.enabled,
        next_run_at=naive_utc(payload.next_run_at),
        interval_seconds=payload.interval_seconds,
        created_by="admin",
    )
    await repo.audit(
        action="scheduled_task_create",
        group_id=task.group_id,
        target_type="scheduled_task",
        target_id=str(task.id),
        detail={"task_type": task.task_type, "schedule_type": task.schedule_type},
    )
    await session.commit()
    return scheduled_task_out(task)


@router.patch(
    "/scheduled-tasks/{task_id}",
    response_model=ScheduledTaskOut,
    dependencies=[Depends(require_admin)],
)
async def update_scheduled_task(
    task_id: Annotated[int, Path(ge=1)],
    payload: ScheduledTaskUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    changes = payload.model_dump(exclude_unset=True)
    if "next_run_at" in changes:
        changes["next_run_at"] = naive_utc(changes["next_run_at"])
    task = await repo.update_scheduled_task_by_id(task_id, changes)
    if task is None:
        raise HTTPException(status_code=404, detail="scheduled task not found")
    await repo.audit(
        action="scheduled_task_update",
        group_id=task.group_id,
        target_type="scheduled_task",
        target_id=str(task.id),
        detail={"changes": audit_safe_detail(changes)},
    )
    await session.commit()
    return scheduled_task_out(task)


@router.delete("/scheduled-tasks/{task_id}", dependencies=[Depends(require_admin)])
async def delete_scheduled_task(
    task_id: Annotated[int, Path(ge=1)],
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    task = await repo.get_scheduled_task_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="scheduled task not found")
    group_id = task.group_id
    deleted = await repo.delete_scheduled_task_by_id(task_id)
    await repo.audit(
        action="scheduled_task_delete",
        group_id=group_id,
        target_type="scheduled_task",
        target_id=str(task_id),
    )
    await session.commit()
    return {"deleted": bool(deleted)}


@router.get("/task-runs", response_model=list[TaskRunOut], dependencies=[Depends(require_admin)])
async def list_task_runs(
    request: Request,
    session: AsyncSession = Depends(get_session),
    task_id: int | None = Query(default=None, ge=1),
):
    repo = repo_from(request, session)
    runs = await repo.list_task_runs(task_id=task_id)
    return [task_run_out(run) for run in runs]


@router.get(
    "/knowledge-docs",
    response_model=list[KnowledgeDocumentOut],
    dependencies=[Depends(require_admin)],
)
async def list_knowledge_docs(
    request: Request,
    session: AsyncSession = Depends(get_session),
    group_id: str | None = Query(default=None, pattern=r"^\d*$"),
):
    repo = repo_from(request, session)
    documents = await repo.list_knowledge_documents(group_id=group_id)
    return [knowledge_document_out(document) for document in documents]


@router.post(
    "/knowledge-docs",
    response_model=KnowledgeDocumentOut,
    dependencies=[Depends(require_admin)],
)
async def create_knowledge_doc(
    payload: KnowledgeDocumentCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    document = await repo.create_knowledge_document(
        group_id=payload.group_id,
        title=payload.title,
        content=payload.content,
        enabled=payload.enabled,
        created_by="admin",
    )
    await repo.audit(
        action="knowledge_doc_create",
        group_id=document.group_id,
        target_type="knowledge_doc",
        target_id=str(document.id),
        detail={"source": "admin", "chunk_count": document.chunk_count},
    )
    await session.commit()
    return knowledge_document_out(document)


@router.patch(
    "/knowledge-docs/{document_id}",
    response_model=KnowledgeDocumentOut,
    dependencies=[Depends(require_admin)],
)
async def update_knowledge_doc(
    document_id: Annotated[int, Path(ge=1)],
    payload: KnowledgeDocumentUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    changes = payload.model_dump(exclude_unset=True)
    document = await repo.update_knowledge_document_by_id(document_id, changes)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document not found")
    await repo.audit(
        action="knowledge_doc_update",
        group_id=document.group_id,
        target_type="knowledge_doc",
        target_id=str(document.id),
        detail={"source": "admin", "changes": changes},
    )
    await session.commit()
    return knowledge_document_out(document)


@router.delete("/knowledge-docs/{document_id}", dependencies=[Depends(require_admin)])
async def delete_knowledge_doc(
    document_id: Annotated[int, Path(ge=1)],
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    document = await repo.get_knowledge_document_by_id(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document not found")
    group_id = document.group_id
    deleted = await repo.delete_knowledge_document_by_id(document_id)
    await repo.audit(
        action="knowledge_doc_delete",
        group_id=group_id,
        target_type="knowledge_doc",
        target_id=str(document_id),
        detail={"source": "admin"},
    )
    await session.commit()
    return {"deleted": bool(deleted)}


@router.post(
    "/knowledge-docs/{document_id}/reindex",
    response_model=KnowledgeDocumentOut,
    dependencies=[Depends(require_admin)],
)
async def reindex_knowledge_doc(
    document_id: Annotated[int, Path(ge=1)],
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    document = await repo.get_knowledge_document_by_id(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document not found")
    await repo.rebuild_knowledge_chunks(document)
    await repo.audit(
        action="knowledge_doc_reindex",
        group_id=document.group_id,
        target_type="knowledge_doc",
        target_id=str(document.id),
        detail={"source": "admin", "chunk_count": document.chunk_count},
    )
    await session.commit()
    return knowledge_document_out(document)


@router.post("/knowledge-search", dependencies=[Depends(require_admin)])
async def search_knowledge(
    payload: KnowledgeSearchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    results = await repo.search_knowledge(
        group_id=payload.group_id,
        query=payload.query,
        limit=payload.limit,
    )
    return {
        "results": [
            {
                "document_id": item.document_id,
                "chunk_id": item.chunk_id,
                "title": item.title,
                "group_id": item.group_id,
                "chunk_index": item.chunk_index,
                "content": item.content,
                "score": item.score,
                "source": item.source,
            }
            for item in results
        ]
    }


@router.get("/memories", response_model=list[MemoryOut], dependencies=[Depends(require_admin)])
async def list_memories(
    request: Request,
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None, pattern=r"^(pending|approved|rejected|deleted)$"),
    group_id: str | None = Query(default=None, pattern=r"^\d*$"),
    user_id: str | None = Query(default=None, pattern=r"^\d*$"),
):
    repo = repo_from(request, session)
    memories = await repo.list_memories_for_admin(status=status, group_id=group_id, user_id=user_id)
    return [memory_out(memory) for memory in memories]


@router.post("/memories", response_model=MemoryOut, dependencies=[Depends(require_admin)])
async def create_memory(
    payload: MemoryCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    memory = await repo.create_memory(
        group_id=payload.group_id,
        user_id=payload.user_id,
        content=payload.content,
        source=payload.source,
        confidence=payload.confidence,
        status=payload.status,
        created_by="admin",
    )
    await repo.audit(
        action="memory_create",
        group_id=memory.group_id,
        target_type="memory",
        target_id=str(memory.id),
        detail={"source": "admin", "status": memory.status},
    )
    await session.commit()
    return memory_out(memory)


@router.patch("/memories/{memory_id}", response_model=MemoryOut, dependencies=[Depends(require_admin)])
async def update_memory(
    memory_id: Annotated[int, Path(ge=1)],
    payload: MemoryUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    changes = payload.model_dump(exclude_unset=True)
    memory = await repo.update_memory_by_id(memory_id, changes)
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    await repo.audit(
        action="memory_update",
        group_id=memory.group_id,
        target_type="memory",
        target_id=str(memory.id),
        detail={"source": "admin", "changes": changes},
    )
    await session.commit()
    return memory_out(memory)


@router.delete("/memories/{memory_id}", dependencies=[Depends(require_admin)])
async def delete_memory(
    memory_id: Annotated[int, Path(ge=1)],
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    memory = await repo.update_memory_by_id(memory_id, {"status": "deleted"})
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    await repo.audit(
        action="memory_delete",
        group_id=memory.group_id,
        target_type="memory",
        target_id=str(memory.id),
        detail={"source": "admin"},
    )
    await session.commit()
    return {"deleted": True}


@router.get("/settings/bot", response_model=BotSettingsOut, dependencies=[Depends(require_admin)])
async def get_bot_settings(request: Request, session: AsyncSession = Depends(get_session)):
    repo = repo_from(request, session)
    return await repo.get_bot_settings()


@router.patch("/settings/bot", response_model=BotSettingsOut, dependencies=[Depends(require_admin)])
async def update_bot_settings(
    payload: BotSettingsUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    await repo.update_bot_settings(payload.model_dump(exclude_unset=True))
    await repo.audit(action="bot_settings_update", target_type="settings", target_id="bot")
    await session.commit()
    return await repo.get_bot_settings()


@router.get("/settings/llm", response_model=LLMSettingsOut, dependencies=[Depends(require_admin)])
async def get_llm_settings(request: Request, session: AsyncSession = Depends(get_session)):
    repo = repo_from(request, session)
    config = await repo.get_llm_config()
    return LLMSettingsOut(
        provider=config.provider,
        base_url=config.base_url,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout_seconds=config.timeout_seconds,
        api_key_configured=bool(config.api_key),
    )


@router.patch("/settings/llm", dependencies=[Depends(require_admin)])
async def update_llm_settings(
    payload: LLMSettingsUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    await repo.update_llm_config(payload.model_dump(exclude_unset=True))
    await repo.audit(action="llm_settings_update", target_type="settings", target_id="llm")
    await session.commit()
    return await get_llm_settings(request, session)


@router.post("/settings/llm/test", dependencies=[Depends(require_admin)])
async def test_llm_settings(
    payload: LLMTestRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = repo_from(request, session)
    result = await request.app.state.llm.chat(repo, payload.prompt, skill_name="admin_test")
    await session.commit()
    return {"status": result.status, "model": result.model, "text": result.text}


@router.get("/system/logs", dependencies=[Depends(require_admin)])
async def logs(request: Request, session: AsyncSession = Depends(get_session)):
    repo = repo_from(request, session)
    messages = await repo.recent_messages()
    return [
        {
            "id": item.id,
            "group_id": item.group_id,
            "user_id": item.user_id,
            "message_id": item.message_id,
            "content": item.content,
            "status": item.status,
            "drop_reason": item.drop_reason,
            "created_at": item.created_at.isoformat(),
        }
        for item in messages
    ]

@router.get("/system/errors", dependencies=[Depends(require_admin)])
async def errors(request: Request, session: AsyncSession = Depends(get_session)):
    repo = repo_from(request, session)
    messages = await repo.recent_errors()
    return [
        {
            "id": item.id,
            "group_id": item.group_id,
            "user_id": item.user_id,
            "message_id": item.message_id,
            "content": item.content,
            "status": item.status,
            "drop_reason": item.drop_reason,
            "created_at": item.created_at.isoformat(),
        }
        for item in messages
    ]


@router.get("/usage/llm", dependencies=[Depends(require_admin)])
async def llm_usage(request: Request, session: AsyncSession = Depends(get_session)):
    repo = repo_from(request, session)
    records = await repo.recent_llm_usage()
    return [
        {
            "id": item.id,
            "group_id": item.group_id,
            "user_id": item.user_id,
            "skill_name": item.skill_name,
            "provider": item.provider,
            "model": item.model,
            "prompt_tokens": item.prompt_tokens,
            "completion_tokens": item.completion_tokens,
            "latency_ms": item.latency_ms,
            "status": item.status,
            "error_message": item.error_message,
            "created_at": item.created_at.isoformat(),
        }
        for item in records
    ]


@router.get("/audit-logs", dependencies=[Depends(require_admin)])
async def audit_logs(request: Request, session: AsyncSession = Depends(get_session)):
    repo = repo_from(request, session)
    records = await repo.recent_audit_logs()
    return [
        {
            "id": item.id,
            "actor_user_id": item.actor_user_id,
            "actor_role": item.actor_role,
            "group_id": item.group_id,
            "action": item.action,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "detail_json": item.detail_json,
            "result": item.result,
            "created_at": item.created_at.isoformat(),
        }
        for item in records
    ]
