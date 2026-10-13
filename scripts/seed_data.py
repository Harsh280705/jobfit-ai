"""Seed demo data: resumes, jobs, evaluation cases."""
from __future__ import annotations
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db.session import SessionLocal, engine, Base  # noqa: E402
import app.models.models  # noqa: F401,E402
from app.models.models import Document, EvaluationCase, EvaluationDataset, JobDescription, Resume  # noqa: E402
from app.services.seed import ensure_skill_seed  # noqa: E402
from sqlalchemy import select  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_skill_seed()
    async with SessionLocal() as s:
        # resumes
        rd = os.path.join(DATA, "sample_resumes")
        jd = os.path.join(DATA, "sample_jobs")
        if os.path.isdir(rd):
            existing = (await s.execute(select(Resume))).scalars().all()
            if not existing:
                for fn in sorted(os.listdir(rd)):
                    if not fn.endswith(".txt"):
                        continue
                    with open(os.path.join(rd, fn), encoding="utf-8") as f:
                        text = f.read()
                    d = Document(document_type="resume", filename=fn, mime_type="text/plain",
                                 storage_path="seed", text_content=text)
                    s.add(d)
                    await s.flush()
                    s.add(Resume(document_id=d.id, raw_text=text))
                await s.commit()
        if os.path.isdir(jd):
            existing = (await s.execute(select(JobDescription))).scalars().all()
            if not existing:
                for fn in sorted(os.listdir(jd)):
                    if not fn.endswith(".txt"):
                        continue
                    with open(os.path.join(jd, fn), encoding="utf-8") as f:
                        text = f.read()
                    d = Document(document_type="job_description", filename=fn, mime_type="text/plain",
                                 storage_path="seed", text_content=text)
                    s.add(d)
                    await s.flush()
                    s.add(JobDescription(document_id=d.id, title=fn.replace(".txt", "").replace("_", " ").title(),
                                         raw_text=text))
                await s.commit()
        # evaluation dataset
        ds = (await s.execute(select(EvaluationDataset))).scalars().first()
        if not ds:
            ds = EvaluationDataset(name="seed", description="Seed requirement-level annotations")
            s.add(ds)
            await s.flush()
            with open(os.path.join(DATA, "evaluation", "cases.json"), encoding="utf-8") as f:
                cases = json.load(f)
            for c in cases:
                s.add(EvaluationCase(dataset_id=ds.id, requirement_text=c["requirement"],
                                     resume_text=c["resume"], expected_status=c["expected_status"],
                                     reason=c.get("reason", ""), category=c.get("category", "general")))
            await s.commit()
            print(f"seeded {len(cases)} evaluation cases")
        print("seed complete")


if __name__ == "__main__":
    asyncio.run(main())
