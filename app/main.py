from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.admin_api import router as admin_router
from app.auth import TokenStore
from app.cache import create_rate_limiter
from app.config import Settings, get_settings
from app.db import create_engine, create_session_factory, init_db
from app.events import normalize_group_message
from app.llm import LLMService
from app.onebot import OneBotConnectionManager, websocket_event_stream
from app.repository import Repository
from app.router import MessageRouter

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        await init_db(app.state.engine)
        app.state.rate_limiter = await create_rate_limiter(settings.redis_url)
        app.state.message_router = MessageRouter(settings, app.state.llm, app.state.rate_limiter)
        try:
            yield
        finally:
            await app.state.engine.dispose()

    app = FastAPI(title="QQBot MVP", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings
    app.state.engine = create_engine(settings)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.onebot = OneBotConnectionManager()
    app.state.llm = LLMService()
    app.state.token_store = TokenStore()

    @app.websocket(settings.onebot_reverse_ws_path)
    async def onebot_ws(websocket: WebSocket) -> None:
        if settings.onebot_access_token:
            token = websocket.headers.get("authorization", "").replace("Bearer ", "")
            if token != settings.onebot_access_token:
                await websocket.close(code=1008)
                return

        await app.state.onebot.attach(websocket)
        try:
            async for payload in websocket_event_stream(websocket):
                event = normalize_group_message(payload, settings)
                if event is None:
                    continue
                async with app.state.session_factory() as session:
                    repo = Repository(session, settings)
                    try:
                        await app.state.message_router.handle(event, repo, app.state.onebot)
                        await session.commit()
                    except Exception as exc:
                        logger.exception("Failed to process OneBot event")
                        await session.rollback()
                        app.state.onebot.status.last_error = str(exc)
        except WebSocketDisconnect:
            app.state.onebot.detach()
        except Exception as exc:
            logger.exception("OneBot websocket crashed")
            app.state.onebot.detach(str(exc))

    app.include_router(admin_router)
    return app


def run() -> None:
    uvicorn.run("app.main:create_app", factory=True, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
