from __future__ import annotations

from sqlalchemy import text

from app.config import Settings
from app.db import create_engine, init_db
from app.migrations import MIGRATIONS


async def test_init_db_records_schema_migrations(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
    )
    engine = create_engine(settings)
    try:
        await init_db(engine)
        async with engine.connect() as conn:
            rows = (
                await conn.execute(text("SELECT revision FROM schema_migrations ORDER BY revision"))
            ).scalars().all()

        assert rows == sorted(migration.revision for migration in MIGRATIONS)
    finally:
        await engine.dispose()
