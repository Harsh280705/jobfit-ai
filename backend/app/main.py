"""FastAPI application entrypoint."""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import router
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create tables on startup (Alembic handles prod migrations; this keeps Docker/dev working)
    from app.db.session import engine
    from app.db.session import Base
    import app.models.models  # noqa: F401  (register tables)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # additive RL columns for pre-existing databases (no-op when present)
        try:
            from app.db.rl_migration import ensure_rl_columns_sync
            await conn.run_sync(ensure_rl_columns_sync)
        except Exception as e:
            logger.warning(f"rl column ensure skipped: {e}")
    # ensure pgvector extension + skill seed data
    try:
        from app.db.session import SessionLocal
        from sqlalchemy import text as _text
        async with SessionLocal() as s:
            try:
                await s.execute(_text("CREATE EXTENSION IF NOT EXISTS vector"))
                await s.commit()
            except Exception:
                await s.rollback()
        from app.services.seed import ensure_skill_seed
        await ensure_skill_seed()
    except Exception as e:
        logger.warning(f"startup seed skipped: {e}")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="JobFit AI", version="1.0.0", lifespan=lifespan)
    # Explicit origins only: never append "*" while allow_credentials=True
    # (browsers reject wildcard+credentials; see docs). Configure prod via
    # BACKEND_CORS_ORIGINS env (comma-separated); dev defaults in config.py.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/")
    async def root():
        return {"service": "jobfit-ai", "docs": "/docs"}

    return app


app = create_app()
