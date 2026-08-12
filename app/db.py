from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import config


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_dir(database_url: str) -> None:
    if "sqlite" not in database_url:
        return
    db_path = database_url.split("///")[-1]
    if db_path and db_path != ":memory:" and "/" in db_path:
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)


_ensure_sqlite_dir(config.database_url)

engine = create_async_engine(config.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    import app.models  # noqa: F401  (register models on the metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _add_missing_columns(conn)
        await _migrate_legacy_student_link(conn)


async def _add_missing_columns(conn) -> None:
    """Lightweight migration: add columns introduced after a table already existed."""
    result = await conn.execute(text("PRAGMA table_info(lessons)"))
    columns = {row[1] for row in result.fetchall()}
    if "link" not in columns:
        await conn.execute(text("ALTER TABLE lessons ADD COLUMN link VARCHAR(500)"))


async def _migrate_legacy_student_link(conn) -> None:
    """One-time move of the old single-recipient link (students.telegram_chat_id)
    into the new recipients table, for databases created before multi-recipient support."""
    result = await conn.execute(text("PRAGMA table_info(students)"))
    student_columns = {row[1] for row in result.fetchall()}
    if "telegram_chat_id" not in student_columns:
        return

    result = await conn.execute(text("SELECT COUNT(*) FROM recipients"))
    if result.scalar() > 0:
        return

    result = await conn.execute(
        text("SELECT telegram_chat_id, telegram_username FROM students WHERE telegram_chat_id IS NOT NULL LIMIT 1")
    )
    row = result.fetchone()
    if row:
        await conn.execute(
            text(
                "INSERT INTO recipients (label, telegram_chat_id, telegram_username, linked_at) "
                "VALUES ('Дочь', :chat_id, :username, CURRENT_TIMESTAMP)"
            ),
            {"chat_id": row[0], "username": row[1]},
        )
