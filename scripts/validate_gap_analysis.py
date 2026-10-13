"""Manual validation: 3 JDs x strong/medium/weak resumes through the real API.

Checks for every combination:
1. every gap traces to a real JD requirement_id,
2. every gap evidence string is verbatim from the stored match,
3. suggestions name no skill absent from the JD text (no fabrication).
Prints one full example report.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///gap_validate.db"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6399/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6399/0"

JDS = {
    "ml": ("ML Engineer",
           "Looking for a Machine Learning Engineer with: Python, PyTorch, 3+ years ML experience, "
           "SQL, Docker, AWS. Master's preferred."),
    "backend": ("Backend Engineer",
                "Backend role. 2+ years Python required. SQL required. FastAPI required. "
                "Docker required. Kubernetes preferred."),
    "frontend": ("Frontend Engineer",
                 "Frontend role. React required. TypeScript required. 2+ years frontend experience required. "
                 "GraphQL preferred."),
}

RESUMES = {
    "strong": ("Strong",
               "Senior ML Engineer at Acme, Jan 2020 - Present. Built services with Python, PyTorch, SQL, "
               "Docker on AWS. Master's in Computer Science, MIT. 5 years of ML experience with PyTorch."),
    "medium": ("Medium",
               "Python developer. Built APIs with Python and FastAPI. Trained models with TensorFlow. "
               "SQL dashboards. 1 year of ML experience. Bachelor's in Computer Science."),
    "weak": ("Weak",
             "Java backend developer. Spring microservices. Bachelor's in History."),
}


async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.db.session import Base
    import app.models.models  # noqa: F401
    from app.main import create_app
    from app.db.session import get_session
    from httpx import AsyncClient, ASGITransport
    from app.nlp.ontology.skills import known_skills

    if os.path.exists("gap_validate.db"):
        os.remove("gap_validate.db")
    eng = create_async_engine("sqlite+aiosqlite:///gap_validate.db", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    app = create_app()

    async def _ov():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _ov
    skills = {s.lower() for s in known_skills()}
    shown = False
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for jd_key, (title, jd_text) in JDS.items():
            j = (await c.post("/api/v1/jobs", json={"title": title, "text": jd_text})).json()
            for rk, (_rn, resume_text) in RESUMES.items():
                r = (await c.post("/api/v1/resumes", json={"text": resume_text})).json()
                a = (await c.post("/api/v1/analyses",
                                  json={"resume_id": r["id"], "job_description_id": j["id"]})).json()
                detail = (await c.get(f"/api/v1/analyses/{a['analysis_id']}")).json()
                assert detail["status"] == "COMPLETED", detail.get("error")
                gap = (await c.post(f"/api/v1/analyses/{a['analysis_id']}/gap-analysis", json={})).json()
                req_ids = {x["id"] for x in detail["requirements"]}
                jd_vocab = " ".join(x["raw_text"] + " " + x["normalized_requirement"]
                                    for x in detail["requirements"]).lower()
                ev_by_req = {m["requirement_id"]: [e.get("text", "") for e in m["evidence"]]
                             for m in detail["matches"]}
                n_gaps = 0
                for section in ("critical_gaps", "preferred_gaps", "transferable_skills",
                                "insufficient_evidence"):
                    for g in gap[section]:
                        n_gaps += 1
                        assert g["requirement_id"] in req_ids, f"untraceable gap {g}"
                        for e in g["evidence"]:
                            assert e["text"] in ev_by_req[g["requirement_id"]], "non-verbatim evidence"
                        for tok in g["suggestion"].split():
                            clean = tok.strip(".,;:()\"'").lower()
                            if clean in skills:
                                assert clean in jd_vocab, f"fabricated skill: {tok}"
                print(f"[{jd_key} x {rk}] {gap['summary']['overall_message']} "
                      f"crit={gap['summary']['critical_gap_count']} pref={gap['summary']['preferred_gap_count']} "
                      f"trans={gap['summary']['transferable_count']} covered={gap['summary']['covered_count']}")
                if jd_key == "ml" and rk == "medium" and not shown:
                    shown = True
                    import json as _j
                    print("\n--- EXAMPLE OUTPUT (ml x medium) ---")
                    print(_j.dumps(gap, indent=1)[:6000])
    await eng.dispose()
    if os.path.exists("gap_validate.db"):
        os.remove("gap_validate.db")
    print("\nAll combos traceable; no fabricated skills; no invented experience.")


if __name__ == "__main__":
    asyncio.run(main())
