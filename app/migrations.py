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


MIGRATIONS: tuple[Migration, ...] = (
    Migration("20260706_001_baseline_schema", "Record baseline schema after MVP create_all", baseline_schema),
    Migration(
        "20260706_002_knowledge_embedding_json",
        "Ensure knowledge chunks can store future vector metadata",
        knowledge_embedding_json,
    ),
)
