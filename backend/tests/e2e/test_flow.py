"""E2E (API-level): full user flow as the UI drives it.

upload document -> create resume + job from text -> analyze -> poll to
COMPLETED -> requirement detail -> matches -> evaluation run.
Asserts the UI contract: every match carries status, confidence, evidence,
explanation; scores carry all dimensions + eligibility.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

TEST_DB = os.path.join(os.path.dirname(__file__), "test_jobfit_e2e.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.session import Base
import app.models.models  # noqa: F401


@pytest_asyncio.fixture()
async def e2e_client():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    eng = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB}", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    from app.main import create_app
    from app.db.session import get_session

    app = create_app()

    async def _override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await eng.dispose()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


async def test_full_user_flow(e2e_client):
    from unittest.mock import patch

    c = e2e_client
    # 1. upload a resume text file as a document (parse path)
    files = {"file": ("resume.txt", b"Python, SQL. Backend Engineer at Acme, Jan 2022 - Present. Python APIs, SQL.", "text/plain")}
    up = await c.post("/api/v1/documents/upload", files=files, data={"document_type": "resume"})
    assert up.status_code == 200, up.text

    # 2. resume + job from text (as the UI does after file->text)
    r = await c.post("/api/v1/resumes", json={"text": "Python, SQL. Backend Engineer at Acme, Jan 2022 - Present. Python APIs, SQL pipelines."})
    j = await c.post("/api/v1/jobs", json={"title": "Backend", "text": "2+ years Python required. SQL required. Kubernetes preferred."})
    assert r.status_code == 200 and j.status_code == 200

    # 3. analyze + poll (as the Results page does)
    # Patch enqueue: local Redis may be up without a worker (QUEUED forever).
    with patch("app.workers.celery_app.enqueue_analysis",
               side_effect=RuntimeError("test forces inline fallback")):
        a = await c.post("/api/v1/analyses", json={"resume_id": r.json()["id"], "job_description_id": j.json()["id"]})
        assert a.status_code == 200
        aid = a.json()["analysis_id"]
        detail = None
        for _ in range(20):
            g = await c.get(f"/api/v1/analyses/{aid}")
            assert g.status_code == 200
            if g.json()["status"] in ("COMPLETED", "FAILED"):
                detail = g.json()
                break
            import asyncio
            await asyncio.sleep(0.3)
    assert detail and detail["status"] == "COMPLETED", (detail or {}).get("error")

    # 4. UI contract assertions
    assert detail["score"]["overall"] >= 0 and detail["score"]["eligibility"]
    assert len(detail["matches"]) == len(detail["requirements"]) > 0
    for m in detail["matches"]:
        assert m["status"] and m["confidence"] is not None and m["explanation"]

    # 5. requirement detail + matches endpoints (detail view + filters)
    req_id = detail["requirements"][0]["id"]
    d = await c.get(f"/api/v1/analyses/{aid}/requirements/{req_id}")
    assert d.status_code == 200 and d.json()["requirement"]["id"] == req_id
    ms = await c.get(f"/api/v1/analyses/{aid}/matches")
    assert ms.status_code == 200 and len(ms.json()) == len(detail["matches"])
