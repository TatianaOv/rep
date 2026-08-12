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


async def _add_missing_columns(conn) -> None:
    """Lightweight migration: add columns introduced after a table already existed."""
    result = await conn.execute(text("PRAGMA table_info(lessons)"))
    columns = {row[1] for row in result.fetchall()}
    if "link" not in columns:
        await conn.execute(text("ALTER TABLE lessons ADD COLUMN link VARCHAR(500)"))
