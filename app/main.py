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
from app.embedding import EmbeddingService
from app.events import normalize_group_message, normalize_group_notice, normalize_private_message
from app.image_generation import ImageGenerationService
from app.llm import LLMService
from app.onebot import OneBotConnectionManager, websocket_event_stream
from app.repository import Repository
from app.router import MessageRouter
from app.scheduler import TaskScheduler
from app.web_search import WebSearchService

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
        app.state.message_router = MessageRouter(
            settings,
            app.state.llm,
            app.state.rate_limiter,
            app.state.image,
            app.state.web_search,
        )
        app.state.task_scheduler = TaskScheduler(
            session_factory=app.state.session_factory,
            settings=settings,
            sender=app.state.onebot,
            cache=app.state.rate_limiter,
            llm=app.state.llm,
        )
        app.state.task_scheduler.start()
        try:
            yield
        finally:
            await app.state.task_scheduler.stop()
            await app.state.rate_limiter.close()
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
    app.state.image = ImageGenerationService()
    app.state.embedding = EmbeddingService()
    app.state.web_search = WebSearchService()
    app.state.token_store = TokenStore()

    @app.websocket(settings.onebot_reverse_ws_path)
    async def onebot_ws(websocket: WebSocket) -> None:
        if settings.onebot_access_token:
            auth_header = websocket.headers.get("authorization", "")
            token = auth_header.removeprefix("Bearer ").strip()
            token = token or websocket.headers.get("x-access-token", "").strip()
            token = token or websocket.query_params.get("access_token", "").strip()
            if token != settings.onebot_access_token:
                await websocket.close(code=1008)
                return

        await app.state.onebot.attach(websocket)
        try:
            async for payload in websocket_event_stream(websocket):
                app.state.onebot.record_event()
                event = normalize_group_message(payload, settings)
                if event is None:
                    event = normalize_private_message(payload, settings)
                notice = normalize_group_notice(payload)
                if event is None:
                    if notice is None:
                        continue
                    async with app.state.session_factory() as session:
                        repo = Repository(session, settings, app.state.embedding)
                        try:
                            await app.state.message_router.handle_group_notice(
                                notice,
                                repo,
                                app.state.onebot,
                            )
                            await session.commit()
                        except Exception as exc:
                            logger.exception("Failed to process OneBot notice")
                            await session.rollback()
                            app.state.onebot.status.last_error = str(exc)
                    continue
                async with app.state.session_factory() as session:
                    repo = Repository(session, settings, app.state.embedding)
                    try:
                        await app.state.message_router.handle(event, repo, app.state.onebot)
                        await session.commit()
                    except Exception as exc:
                        logger.exception("Failed to process OneBot event")
                        await session.rollback()
                        app.state.onebot.status.last_error = str(exc)
        except WebSocketDisconnect:
            app.state.onebot.detach(websocket=websocket)
        except Exception as exc:
            logger.exception("OneBot websocket crashed")
            app.state.onebot.detach(str(exc), websocket)

    app.include_router(admin_router)
    return app


def run() -> None:
    uvicorn.run("app.main:create_app", factory=True, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
