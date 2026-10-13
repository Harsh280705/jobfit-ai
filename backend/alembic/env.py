"""Alembic env (async)."""
from __future__ import annotations
import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings
from app.db.session import Base
import app.models.models  # noqa

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=get_settings().DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_async_engine(get_settings().DATABASE_URL, future=True)
    asyncio.run(_migrate(engine))


async def _migrate(engine):
    from sqlalchemy import text
    async with engine.connect() as conn:
        await conn.run_sync(do_migrate)


def do_migrate(conn):
    context.configure(connection=conn, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
