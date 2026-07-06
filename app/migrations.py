from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection


MigrationFn = Callable[[AsyncConnection], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Migration:
    revision: str
    description: str
    apply: MigrationFn


async def run_migrations(conn: AsyncConnection) -> None:
    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                revision VARCHAR(64) PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    applied = set(
        (
            await conn.execute(text("SELECT revision FROM schema_migrations"))
        ).scalars()
    )
    for migration in MIGRATIONS:
        if migration.revision in applied:
            continue
        await migration.apply(conn)
        await conn.execute(
            text(
                """
                INSERT INTO schema_migrations (revision, description)
                VALUES (:revision, :description)
                """
            ),
            {"revision": migration.revision, "description": migration.description},
        )


async def column_exists(conn: AsyncConnection, table_name: str, column_name: str) -> bool:
    def inspect_columns(sync_conn) -> bool:
        inspector = inspect(sync_conn)
        if not inspector.has_table(table_name):
            return False
        return any(column["name"] == column_name for column in inspector.get_columns(table_name))

    return await conn.run_sync(inspect_columns)


async def add_column_if_missing(conn: AsyncConnection, table_name: str, column_sql: str) -> None:
    column_name = column_sql.split()[0]
    if not await column_exists(conn, table_name, column_name):
        await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))


async def baseline_schema(conn: AsyncConnection) -> None:
    return None


async def knowledge_embedding_json(conn: AsyncConnection) -> None:
    await add_column_if_missing(
        conn,
        "knowledge_chunks",
        "embedding_json TEXT DEFAULT '[]'",
    )


async def scheduled_task_tables(conn: AsyncConnection) -> None:
    from app.models import ScheduledTask, TaskRun

    def create_tables(sync_conn) -> None:
        ScheduledTask.__table__.create(sync_conn, checkfirst=True)
        TaskRun.__table__.create(sync_conn, checkfirst=True)

    await conn.run_sync(create_tables)


async def skill_settings_table(conn: AsyncConnection) -> None:
    from app.models import SkillSetting

    def create_tables(sync_conn) -> None:
        SkillSetting.__table__.create(sync_conn, checkfirst=True)

    await conn.run_sync(create_tables)


async def game_states_table(conn: AsyncConnection) -> None:
    from app.models import GameState

    def create_tables(sync_conn) -> None:
        GameState.__table__.create(sync_conn, checkfirst=True)

    await conn.run_sync(create_tables)


async def knowledge_pgvector_support(conn: AsyncConnection) -> None:
    if conn.dialect.name != "postgresql":
        return
    try:
        async with conn.begin_nested():
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await add_column_if_missing(
                conn,
                "knowledge_chunks",
                "embedding_vector vector(64)",
            )
    except Exception:
        return


async def knowledge_file_metadata(conn: AsyncConnection) -> None:
    await add_column_if_missing(
        conn,
        "knowledge_documents",
        "source_file_name VARCHAR(255) DEFAULT ''",
    )
    await add_column_if_missing(
        conn,
        "knowledge_documents",
        "source_file_path VARCHAR(500) DEFAULT ''",
    )
    await add_column_if_missing(
        conn,
        "knowledge_documents",
        "source_locator VARCHAR(255) DEFAULT ''",
    )


async def knowledge_ai_map_metadata(conn: AsyncConnection) -> None:
    await add_column_if_missing(
        conn,
        "knowledge_documents",
        "ai_summary TEXT DEFAULT ''",
    )
    await add_column_if_missing(
        conn,
        "knowledge_documents",
        "ai_keywords_json TEXT DEFAULT '[]'",
    )
    await add_column_if_missing(
        conn,
        "knowledge_documents",
        "ai_questions_json TEXT DEFAULT '[]'",
    )
    await add_column_if_missing(
        conn,
        "knowledge_documents",
        "ai_index_status VARCHAR(32) DEFAULT 'pending'",
    )


MIGRATIONS: tuple[Migration, ...] = (
    Migration("20260706_001_baseline_schema", "Record baseline schema after MVP create_all", baseline_schema),
    Migration(
        "20260706_002_knowledge_embedding_json",
        "Ensure knowledge chunks can store future vector metadata",
        knowledge_embedding_json,
    ),
    Migration(
        "20260706_003_scheduled_tasks",
        "Record scheduled task and task run tables",
        scheduled_task_tables,
    ),
    Migration(
        "20260706_004_skill_settings",
        "Create global and group skill settings",
        skill_settings_table,
    ),
    Migration(
        "20260706_005_game_states",
        "Create persistent game state table",
        game_states_table,
    ),
    Migration(
        "20260706_006_knowledge_pgvector_support",
        "Enable pgvector column for knowledge chunks when available",
        knowledge_pgvector_support,
    ),
    Migration(
        "20260706_007_knowledge_file_metadata",
        "Store source file metadata for imported knowledge documents",
        knowledge_file_metadata,
    ),
    Migration(
        "20260706_008_knowledge_ai_map_metadata",
        "Store AI generated knowledge map metadata",
        knowledge_ai_map_metadata,
    ),
)
