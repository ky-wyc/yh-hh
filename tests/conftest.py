from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.cache import MemoryRateLimiter
from app.config import Settings
from app.db import create_engine, create_session_factory, init_db
from app.llm import LLMService
from app.onebot import MemoryOneBotSender
from app.repository import Repository
from app.router import MessageRouter


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ALLOWED_GROUPS="10001",
        BOT_QQ="123456",
        LLM_API_KEY="",
    )


@pytest.fixture
async def session_factory(settings: Settings):
    engine = create_engine(settings)
    await init_db(engine)
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


@pytest.fixture
async def repo(session_factory: async_sessionmaker, settings: Settings):
    session = session_factory()
    try:
        yield Repository(session, settings)
        await session.commit()
    finally:
        await session.close()


@pytest.fixture
def sender() -> MemoryOneBotSender:
    return MemoryOneBotSender()


@pytest.fixture
def llm() -> LLMService:
    return LLMService()


@pytest.fixture
def message_router(settings: Settings, llm: LLMService) -> MessageRouter:
    return MessageRouter(settings, llm, MemoryRateLimiter())
