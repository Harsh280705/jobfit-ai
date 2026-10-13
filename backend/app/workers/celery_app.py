"""Celery app. Falls back to eager synchronous execution when Redis is unavailable."""
from __future__ import annotations
import asyncio
from app.core.config import get_settings

settings = get_settings()

try:
    from celery import Celery  # type: ignore

    celery = Celery("jobfit", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)
    celery.conf.update(task_track_started=True)

    @celery.task(name="jobfit.run_analysis", bind=True)
    def run_analysis_task(self, analysis_id: str):
        from app.db.session import SessionLocal
        from app.services.analysis import run_analysis

        async def _go():
            async with SessionLocal() as session:
                await run_analysis(session, analysis_id)

        asyncio.run(_go())
        return {"analysis_id": analysis_id, "status": "done"}

    def _redis_reachable(timeout: float = 0.5) -> bool:
        import socket
        from urllib.parse import urlparse

        try:
            u = urlparse(settings.CELERY_BROKER_URL)
            s = socket.create_connection((u.hostname or "localhost", u.port or 6379), timeout=timeout)
            s.close()
            return True
        except Exception:
            return False

    def enqueue_analysis(analysis_id: str) -> str:
        # Fast-fail when the broker is unreachable (dev laptop without Redis):
        # raise immediately so the API route falls back to inline `await run_analysis(...)`.
        # Never asyncio.run() here — the caller is already inside a running event loop.
        if not _redis_reachable():
            raise RuntimeError("redis broker unreachable; caller should run inline")
        r = run_analysis_task.delay(analysis_id)
        return str(r.id)

except ImportError:  # celery not installed

    class _Fake:  # type: ignore
        def delay(self, *a, **k):
            raise RuntimeError("celery unavailable")

    run_analysis_task = _Fake()  # type: ignore
    celery = None  # type: ignore

    def enqueue_analysis(analysis_id: str) -> str:
        # No celery installed: caller (async route) runs inline with its own session.
        raise RuntimeError("celery unavailable; caller should run inline")
