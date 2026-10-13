"""Versioned API: documents, resumes, jobs, analyses, requirements, matches, evaluation, health."""
from __future__ import annotations
import json
import mimetypes
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import UnsupportedFormatError
from app.db.session import get_session
from app.models.models import (Analysis, AnalysisScore, Document, EvaluationCase, EvaluationDataset,
                               JobDescription, JobRequirement, RequirementMatch, Resume)
from app.schemas.schemas import AnalysisCreate

router = APIRouter(prefix="/api/v1")
ALLOWED = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".txt": "text/plain"}


def _ext(name: str) -> str:
    n = (name or "").lower()
    for e in ALLOWED:
        if n.endswith(e):
            return e
    return ""


def _match_out(m) -> dict:
    """Serialize a RequirementMatch row; rl_* keys are additive (None/False for pre-RL rows)."""
    base_status = getattr(m, "existing_status", None) or m.status
    return {"requirement_id": m.requirement_id, "status": m.status, "confidence": m.confidence,
            "direct_match": m.direct_match, "transferable_match": m.transferable_match,
            "evidence": json.loads(m.evidence or "[]"), "explanation": m.explanation,
            "estimated_years": m.estimated_years,
            "existing_status": base_status,
            "rl_status": getattr(m, "rl_status", None),
            "final_status": m.status,
            "rl_confidence": getattr(m, "rl_confidence", None),
            "rl_changed_decision": bool(getattr(m, "rl_changed", False)),
            "rl_used": bool(getattr(m, "rl_used", False))}


@router.get("/health")
async def health():
    return {"status": "ok", "service": "jobfit-ai"}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(select(Analysis).limit(1))
        return {"ready": True}
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database not ready")


# ---- Documents ----
@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), document_type: str = Form("resume"),
                         session: AsyncSession = Depends(get_session)):
    from app.core.config import get_settings
    from app.nlp.parsers.documents import DocumentParser
    from app.services.storage import get_storage

    settings = get_settings()
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    ext = _ext(file.filename or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported file format.")
    try:
        parsed = DocumentParser().parse(data, file.filename or "upload", file.content_type or ALLOWED[ext])
    except Exception:
        raise HTTPException(status_code=422, detail="Unable to extract text from document.")
    path = get_storage().save(data, file.filename or "upload.bin")
    doc = Document(document_type=document_type, filename=(file.filename or "upload")[:512],
                   mime_type=file.content_type or ALLOWED[ext], storage_path=path,
                   text_content=parsed["text"][:200000])
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return {"id": doc.id, "document_type": doc.document_type, "filename": doc.filename, "mime_type": doc.mime_type}


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, session: AsyncSession = Depends(get_session)):
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return {"id": doc.id, "document_type": doc.document_type, "filename": doc.filename,
            "mime_type": doc.mime_type, "text": doc.text_content[:20000]}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, session: AsyncSession = Depends(get_session)):
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    await session.delete(doc)
    await session.commit()
    return {"deleted": True}


# ---- Resumes / Jobs ----
@router.post("/resumes")
async def create_resume(payload: dict, session: AsyncSession = Depends(get_session)):
    text = (payload.get("text") or "").strip()
    if payload.get("document_id"):
        doc = await session.get(Document, payload["document_id"])
        if not doc:
            raise HTTPException(404, "Document not found")
        text = doc.text_content
    if not text:
        raise HTTPException(400, "Resume text is required")
    doc = Document(document_type="resume", filename="pasted-resume.txt", mime_type="text/plain",
                   storage_path="inline", text_content=text[:200000])
    session.add(doc)
    await session.flush()
    resume = Resume(document_id=doc.id, raw_text=text[:200000])
    session.add(resume)
    await session.commit()
    await session.refresh(resume)
    return {"id": resume.id, "raw_text": resume.raw_text[:5000]}


@router.get("/resumes/{resume_id}")
async def get_resume(resume_id: str, session: AsyncSession = Depends(get_session)):
    r = await session.get(Resume, resume_id)
    if not r:
        raise HTTPException(404, "Resume not found")
    return {"id": r.id, "raw_text": r.raw_text}


@router.post("/jobs")
async def create_job(payload: dict, session: AsyncSession = Depends(get_session)):
    text = (payload.get("text") or "").strip()
    title = (payload.get("title") or "Untitled role")[:512]
    doc_id = payload.get("document_id")
    if doc_id:
        doc = await session.get(Document, doc_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        text = doc.text_content
        doc_id_ref = doc.id
    else:
        d = Document(document_type="job_description", filename="pasted-jd.txt", mime_type="text/plain",
                     storage_path="inline", text_content=text[:200000])
        session.add(d)
        await session.flush()
        doc_id_ref = d.id
    if not text:
        raise HTTPException(400, "Job description text is required")
    job = JobDescription(document_id=doc_id_ref, title=title, raw_text=text[:200000])
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return {"id": job.id, "title": job.title, "raw_text": job.raw_text[:8000]}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)):
    j = await session.get(JobDescription, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return {"id": j.id, "title": j.title, "raw_text": j.raw_text}


# ---- Analyses ----
@router.post("/analyses")
async def create_analysis(payload: dict, session: AsyncSession = Depends(get_session)):
    resume_id = payload.get("resume_id")
    job_id = payload.get("job_description_id") or payload.get("job_id")
    if not resume_id or not job_id:
        raise HTTPException(400, "resume_id and job_description_id are required")
    if not await session.get(Resume, resume_id):
        raise HTTPException(404, "Resume not found")
    if not await session.get(JobDescription, job_id):
        raise HTTPException(404, "Job not found")
    a = Analysis(resume_id=resume_id, job_id=job_id, status="QUEUED", progress=0)
    session.add(a)
    await session.commit()
    await session.refresh(a)
    # enqueue (falls back to inline when broker unavailable)
    try:
        from app.workers.celery_app import enqueue_analysis
        enqueue_analysis(a.id)
    except Exception:
        from app.services.analysis import run_analysis
        await run_analysis(session, a.id)
        await session.refresh(a)
    return {"analysis_id": a.id, "status": a.status}


@router.get("/analyses")
async def list_analyses(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Analysis).order_by(desc(Analysis.created_at)).limit(50))).scalars().all()
    out = []
    for a in rows:
        score = (await session.execute(select(AnalysisScore).where(AnalysisScore.analysis_id == a.id))).scalars().first()
        out.append({"id": a.id, "status": a.status, "progress": a.progress,
                    "overall": score.overall if score else None,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "resume_id": a.resume_id, "job_id": a.job_id})
    return out


@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: str, session: AsyncSession = Depends(get_session)):
    a = await session.get(Analysis, analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found")
    score = (await session.execute(select(AnalysisScore).where(AnalysisScore.analysis_id == a.id))).scalars().first()
    reqs = (await session.execute(select(JobRequirement).where(JobRequirement.job_id == a.job_id))).scalars().all()
    matches = (await session.execute(select(RequirementMatch).where(RequirementMatch.analysis_id == a.id))).scalars().all()
    return {
        "id": a.id, "status": a.status, "progress": a.progress, "error": a.error,
        "timings": json.loads(a.timings or "{}"),
        "score": ({k: getattr(score, k) for k in
                   ["overall", "mandatory_coverage", "preferred_coverage", "experience_fit", "skill_fit",
                    "transferability", "evidence_confidence", "eligibility", "mandatory_total",
                    "mandatory_satisfied", "mandatory_partial", "mandatory_missing"]} if score else None),
        "requirements": [{"id": r.id, "raw_text": r.raw_text, "normalized_requirement": r.normalized_requirement,
                           "category": r.category, "mandatory": r.mandatory, "preference": r.preference,
                           "operator": r.operator, "minimum_years": r.minimum_years,
                           "confidence": r.confidence, "logic_group": r.logic_group} for r in reqs],
        "matches": [_match_out(m) for m in matches],
    }


@router.delete("/analyses/{analysis_id}")
async def delete_analysis(analysis_id: str, session: AsyncSession = Depends(get_session)):
    a = await session.get(Analysis, analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found")
    await session.delete(a)
    await session.commit()
    return {"deleted": True}


@router.get("/analyses/{analysis_id}/requirements")
async def analysis_requirements(analysis_id: str, session: AsyncSession = Depends(get_session)):
    a = await session.get(Analysis, analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found")
    reqs = (await session.execute(select(JobRequirement).where(JobRequirement.job_id == a.job_id))).scalars().all()
    return [{"id": r.id, "raw_text": r.raw_text, "normalized_requirement": r.normalized_requirement,
             "category": r.category, "mandatory": r.mandatory, "preference": r.preference,
             "operator": r.operator, "minimum_years": r.minimum_years, "confidence": r.confidence} for r in reqs]


@router.get("/analyses/{analysis_id}/requirements/{req_id}")
async def requirement_detail(analysis_id: str, req_id: str, session: AsyncSession = Depends(get_session)):
    a = await session.get(Analysis, analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found")
    req = await session.get(JobRequirement, req_id)
    m = (await session.execute(select(RequirementMatch).where(
        RequirementMatch.analysis_id == analysis_id, RequirementMatch.requirement_id == req_id))).scalars().first()
    if not req:
        raise HTTPException(404, "Requirement not found")
    return {"requirement": {"id": req.id, "raw_text": req.raw_text,
                            "normalized_requirement": req.normalized_requirement, "category": req.category,
                            "mandatory": req.mandatory, "minimum_years": req.minimum_years},
            "match": (_match_out(m) if m else None)}


@router.get("/analyses/{analysis_id}/matches")
async def analysis_matches(analysis_id: str, session: AsyncSession = Depends(get_session)):
    ms = (await session.execute(select(RequirementMatch).where(RequirementMatch.analysis_id == analysis_id))).scalars().all()
    return [_match_out(m) for m in ms]


# ---- Resume Gap Analysis (derivation over stored requirement matches; no re-matching) ----
@router.post("/analyses/{analysis_id}/gap-analysis")
async def analysis_gap_report(analysis_id: str, session: AsyncSession = Depends(get_session)):
    from app.nlp.gap.analyzer import build_gap_report
    from app.schemas.schemas import GapAnalysisOut

    a = await session.get(Analysis, analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found")
    if a.status != "COMPLETED":
        raise HTTPException(409, "Gap analysis requires a COMPLETED analysis")
    reqs = (await session.execute(select(JobRequirement).where(JobRequirement.job_id == a.job_id))).scalars().all()
    matches = (await session.execute(select(RequirementMatch).where(RequirementMatch.analysis_id == a.id))).scalars().all()
    req_dicts = [{"id": r.id, "raw_text": r.raw_text, "normalized_requirement": r.normalized_requirement,
                  "category": r.category, "mandatory": r.mandatory, "preference": r.preference,
                  "operator": r.operator, "minimum_years": r.minimum_years,
                  "maximum_years": r.maximum_years, "confidence": r.confidence,
                  "logic_group": r.logic_group} for r in reqs]
    match_dicts = [{"requirement_id": m.requirement_id, "status": m.status, "confidence": m.confidence,
                    "direct_match": m.direct_match, "transferable_match": m.transferable_match,
                    "evidence": json.loads(m.evidence or "[]"), "explanation": m.explanation,
                    "estimated_years": m.estimated_years} for m in matches]
    report = build_gap_report(req_dicts, match_dicts)
    return GapAnalysisOut(analysis_id=a.id, **report).model_dump()


# ---- Evaluation ----
@router.post("/evaluation/run")
async def run_evaluation(payload: dict | None = None, session: AsyncSession = Depends(get_session)):
    from app.nlp.rl.evaluate import evaluate_all

    ds = (await session.execute(select(EvaluationDataset))).scalars().first()
    if not ds:
        raise HTTPException(404, "No evaluation dataset. Run scripts/seed_data.py first.")
    cases = (await session.execute(select(EvaluationCase).where(EvaluationCase.dataset_id == ds.id))).scalars().all()
    case_dicts = [{"requirement_text": c.requirement_text, "resume_text": c.resume_text,
                   "expected_status": c.expected_status, "reason": c.reason, "category": c.category} for c in cases]

    # RL policy is optional: evaluation always reports the baseline + existing
    # matcher, and adds the RL comparison only when a model file is present.
    policy, rl_config, rl_used, split = None, None, False, {}
    try:
        from app.nlp.rl.config import RLConfig
        from app.nlp.rl.inference import load_policy
        rl_config = RLConfig.from_env()
        policy = load_policy(config=rl_config)
        if policy is not None:
            rl_used = True
            try:
                import json as _json
                from app.nlp.rl.inference import resolve_model_path
                with open(resolve_model_path(rl_config), encoding="utf-8") as f:
                    meta = _json.load(f).get("train_metadata", {})
                split = {"train_size": meta.get("n_train_real"),
                         "test_size": len(meta.get("test_indices", [])),
                         "test_indices": meta.get("test_indices", [])}
            except Exception:
                split = {}
    except Exception:
        policy = None

    payload_out = evaluate_all(case_dicts, include_rl=rl_used, policy=policy, config=rl_config)
    # held-out check: score RL only on the training-excluded indices when known
    if rl_used and split.get("test_indices") and len(split["test_indices"]) < len(case_dicts):
        held = [case_dicts[i] for i in split["test_indices"] if 0 <= i < len(case_dicts)]
        payload_out["held_out"] = evaluate_all(held, include_rl=True, policy=policy, config=rl_config)
    else:
        payload_out["held_out"] = {}
    return {"dataset": ds.name, "n_cases": len(case_dicts), "results": payload_out["results"],
            "ablation": payload_out.get("ablation", {}),
            "fine_grained": payload_out.get("fine_grained", {}),
            "held_out": payload_out.get("held_out", {}),
            "rl": {"used": rl_used, "split": split}}


@router.get("/evaluation/results")
async def evaluation_results(session: AsyncSession = Depends(get_session)):
    ds = (await session.execute(select(EvaluationDataset))).scalars().first()
    if not ds:
        return {"dataset": None, "cases": []}
    cases = (await session.execute(select(EvaluationCase).where(EvaluationCase.dataset_id == ds.id).limit(200))).scalars().all()
    return {"dataset": ds.name, "cases": [
        {"requirement": c.requirement_text, "resume": c.resume_text[:300],
         "expected_status": c.expected_status, "category": c.category} for c in cases]}
