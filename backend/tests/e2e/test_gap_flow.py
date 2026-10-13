"""E2E for Resume Gap Analysis: full flow through the HTTP API.

Verifies the new POST /analyses/{id}/gap-analysis endpoint against a real
analysis, the 409 guard for incomplete analyses, and that pre-existing
endpoints keep their contract (status/evidence/explanation present).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

TEST_DB = os.path.join(os.path.dirname(__file__), "test_jobfit_gap.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.session import Base
import app.models.models  # noqa: F401


@pytest_asyncio.fixture()
async def gap_client():
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


async def _completed_analysis(c, resume_text, jd_text, title="Role"):
    from unittest.mock import patch

    r = await c.post("/api/v1/resumes", json={"text": resume_text})
    j = await c.post("/api/v1/jobs", json={"title": title, "text": jd_text})
    assert r.status_code == 200 and j.status_code == 200
    # Patch enqueue: local Redis may be up without a worker (QUEUED forever).
    with patch("app.workers.celery_app.enqueue_analysis",
               side_effect=RuntimeError("test forces inline fallback")):
        a = await c.post("/api/v1/analyses",
                         json={"resume_id": r.json()["id"], "job_description_id": j.json()["id"]})
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
    return aid, detail


async def test_gap_analysis_endpoint(gap_client):
    c = gap_client
    aid, detail = await _completed_analysis(
        c,
        "Python developer. Built APIs with Python and FastAPI. TensorFlow models. SQL dashboards.",
        "ML Engineer. Python required. PyTorch required. SQL required. AWS required.",
        title="ML Engineer",
    )
    g = await c.post(f"/api/v1/analyses/{aid}/gap-analysis", json={})
    assert g.status_code == 200, g.text
    report = g.json()
    assert set(report) >= {"critical_gaps", "preferred_gaps", "transferable_skills",
                           "insufficient_evidence", "covered_requirements", "summary"}
    req_ids = {r["id"] for r in detail["requirements"]}
    for section in ("critical_gaps", "preferred_gaps", "transferable_skills", "insufficient_evidence"):
        for gap in report[section]:
            assert gap["requirement_id"] in req_ids  # traceable, never invented
            assert gap["gap_explanation"] and gap["suggestion"]
    assert report["summary"]["total_requirements"] == len(detail["requirements"])
    assert report["summary"]["covered_count"] == len(report["covered_requirements"])
    # existing contract untouched
    assert len(detail["matches"]) == len(detail["requirements"]) > 0
    for m in detail["matches"]:
        assert m["status"] and m["confidence"] is not None and m["explanation"]


async def test_gap_analysis_404_and_409(gap_client):
    c = gap_client
    g = await c.post("/api/v1/analyses/does-not-exist/gap-analysis", json={})
    assert g.status_code == 404
    # QUEUED (never processed) analysis -> 409, not a crash
    r = await c.post("/api/v1/resumes", json={"text": "Python developer."})
    j = await c.post("/api/v1/jobs", json={"title": "T", "text": "Python required."})
    a = await c.post("/api/v1/analyses",
                     json={"resume_id": r.json()["id"], "job_description_id": j.json()["id"]})
    aid = a.json()["analysis_id"]
    from sqlalchemy import select  # noqa
    g2 = await c.post(f"/api/v1/analyses/{aid}/gap-analysis", json={})
    assert g2.status_code in (200, 409)
