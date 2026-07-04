from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import login, require_admin
from app.repository import Repository
from app.schemas import (
    BotSettingsOut,
    BotSettingsUpdate,
    GroupUpdate,
    LLMSettingsOut,
    LLMSettingsUpdate,
    LLMTestRequest,
    LoginRequest,
    LoginResponse,
)

router = APIRouter(prefix="/api")


async def get_session(request: Request) -> AsyncSession:
    async with request.app.state.session_factory() as session:
        yield session


def repo_from(request: Request, session: AsyncSession) -> Repository:
    return Repository(session, request.app.state.settings)


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
    qq_group_id: str,
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
