"""Integration: extraction -> analysis pipeline -> persistence -> result API (SQLite file DB).

Avoids Redis/Celery and app-lifespan engine games: exercises the real
run_analysis service plus the real FastAPI routes with a dependency override.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

TEST_DB = os.path.join(os.path.dirname(__file__), "test_jobfit_integ.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.session import Base
import app.models.models  # noqa: F401
from app.models.models import Analysis, Document, JobDescription, Resume


@pytest_asyncio.fixture()
async def session_factory():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    eng = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB}", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    yield factory
    await eng.dispose()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


async def _make_pair(session_factory, resume_text, job_text, title="ML Engineer"):
    async with session_factory() as s:
        d1 = Document(document_type="resume", filename="r.txt", mime_type="text/plain",
                      storage_path="inline", text_content=resume_text)
        s.add(d1)
        await s.flush()
        r = Resume(document_id=d1.id, raw_text=resume_text)
        s.add(r)
        await s.flush()
        d2 = Document(document_type="job_description", filename="j.txt", mime_type="text/plain",
                      storage_path="inline", text_content=job_text)
        s.add(d2)
        await s.flush()
        j = JobDescription(document_id=d2.id, title=title, raw_text=job_text)
        s.add(j)
        await s.flush()
        a = Analysis(resume_id=r.id, job_id=j.id, status="QUEUED", progress=0)
        s.add(a)
        await s.commit()
        return a.id


async def test_pipeline_end_to_end(session_factory):
    from app.services.analysis import run_analysis

    resume_text = "Python, PyTorch, SQL. ML Engineer at X, Jan 2022 - Present. Built models with Python and PyTorch. SQL pipelines."
    job_text = "3+ years Python required. PyTorch or TensorFlow preferred. Strong SQL required."
    aid = await _make_pair(session_factory, resume_text, job_text)
    async with session_factory() as s:
        await run_analysis(s, aid)
    async with session_factory() as s:
        a = await s.get(Analysis, aid)
        assert a.status == "COMPLETED", a.error
        from sqlalchemy import select
        from app.models.models import AnalysisScore, RequirementMatch

        score = (await s.execute(select(AnalysisScore).where(AnalysisScore.analysis_id == aid))).scalars().first()
        matches = (await s.execute(select(RequirementMatch).where(RequirementMatch.analysis_id == aid))).scalars().all()
        assert score is not None and score.overall >= 0
        assert len(matches) > 0
        for m in matches:
            assert m.explanation, "every decision must be explained"


async def test_acceptance_scenario_pipeline(session_factory):
    from app.services.analysis import run_analysis

    resume_text = "Python. TensorFlow. Machine Learning Engineer Jan 2025 - Present, TensorFlow and Python. Bachelor's degree."
    job_text = "3+ years Python required. PyTorch required. 3+ years Machine Learning required. Master's preferred. Python AND SQL required."
    aid = await _make_pair(session_factory, resume_text, job_text)
    async with session_factory() as s:
        await run_analysis(s, aid)
    async with session_factory() as s:
        from sqlalchemy import select
        from app.models.models import JobRequirement, RequirementMatch

        a = await s.get(Analysis, aid)
        assert a.status == "COMPLETED", a.error
        reqs = (await s.execute(select(JobRequirement).where(JobRequirement.job_id == a.job_id))).scalars().all()
        matches = (await s.execute(select(RequirementMatch).where(RequirementMatch.analysis_id == aid))).scalars().all()
        assert len(matches) == len(reqs) > 0
        assert all(m.explanation for m in matches)


async def test_api_routes_with_override(session_factory):
    from unittest.mock import patch
    from app.main import create_app
    from app.db.session import get_session

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    # Force inline execution: local Redis may be up without a worker, which
    # would leave the analysis QUEUED. Patching enqueue to raise exercises the
    # route's documented inline fallback deterministically.
    with patch("app.workers.celery_app.enqueue_analysis",
               side_effect=RuntimeError("test forces inline fallback")):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post("/api/v1/resumes", json={"text": "Python backend with FastAPI."})
            assert r.status_code == 200, r.text
            j = await client.post("/api/v1/jobs", json={"title": "Backend", "text": "Python required. SQL preferred."})
            assert j.status_code == 200, j.text
            a = await client.post("/api/v1/analyses",
                                  json={"resume_id": r.json()["id"], "job_description_id": j.json()["id"]})
            assert a.status_code == 200, a.text
            aid = a.json()["analysis_id"]
            # inline fallback runs synchronously; poll once for COMPLETED
            for _ in range(20):
                g = await client.get(f"/api/v1/analyses/{aid}")
                assert g.status_code == 200
                if g.json()["status"] in ("COMPLETED", "FAILED"):
                    break
                import asyncio
                await asyncio.sleep(0.3)
            detail = (await client.get(f"/api/v1/analyses/{aid}")).json()
            assert detail["status"] == "COMPLETED", detail.get("error")
            assert detail["score"] is not None
    app.dependency_overrides.clear()
