"""Analysis pipeline: parse -> extract -> match -> score -> persist. Used by API + Celery worker."""
from __future__ import annotations
import json
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.models import (Analysis, AnalysisScore, CandidateEducation, CandidateExperience,
                               CandidateProfile, CandidateSkill, CandidateEvidence, JobDescription,
                               JobRequirement, RequirementGroup, RequirementMatch, Resume)

logger = get_logger(__name__)


def _maybe_apply_rl(req_dicts: list[dict], base_matches: list[dict],
                    skills: list[dict], experiences: list[dict],
                    resume_text: str, thresholds: dict, settings) -> list[dict]:
    """Apply the RL decision layer when enabled and a model is available.

    Falls back to the deterministic base matches unchanged otherwise —
    existing behavior is preserved byte-for-byte in that case.
    """
    if not getattr(settings, "RL_ENABLED", True):
        return base_matches
    try:
        from app.nlp.rl.config import RLConfig
        from app.nlp.rl.inference import decide_requirement, load_policy
        cfg = RLConfig.from_env()
        cfg.transferable_threshold = thresholds.get("transferable", cfg.transferable_threshold)
        cfg.semantic_threshold = thresholds.get("semantic", cfg.semantic_threshold)
        cfg.min_confidence_to_override = getattr(
            settings, "RL_MIN_OVERRIDE_CONF", cfg.min_confidence_to_override)
        policy = load_policy(config=cfg)
        if policy is None:
            return base_matches
        by_id = {r.get("id"): r for r in req_dicts}
        out = []
        for m in base_matches:
            req = by_id.get(m.get("requirement_id"))
            if req is None:
                out.append(m)
                continue
            try:
                out.append(decide_requirement(req, skills, experiences, resume_text,
                                              m, policy, cfg))
            except Exception:
                logger.warning("RL decide failed; using base decision")
                out.append(m)
        return out
    except Exception:
        logger.warning("RL layer unavailable; using base matcher")
        return base_matches


async def run_analysis(session: AsyncSession, analysis_id: str) -> None:
    from app.core.config import get_settings
    from app.nlp.parsers.documents import segment_sections
    from app.nlp.extractors import resume as resume_ext
    from app.nlp.extractors.requirements import extract_requirements
    from app.nlp.matcher.engine import match_requirement
    from app.nlp.matcher.scoring import compute_scores

    settings = get_settings()
    t0 = time.perf_counter()
    timings: dict[str, float] = {}
    analysis = await session.get(Analysis, analysis_id)
    if analysis is None:
        return
    try:
        analysis.status = "PROCESSING"; analysis.progress = 5
        await session.commit()

        resume = await session.get(Resume, analysis.resume_id)
        job = await session.get(JobDescription, analysis.job_id)
        assert resume and job

        # --- candidate extraction ---
        t = time.perf_counter()
        sections = segment_sections(resume.raw_text)
        profile = resume_ext.extract_profile(resume.raw_text)
        skills = resume_ext.extract_skills(resume.raw_text, sections)
        experiences = resume_ext.extract_experience(resume.raw_text, sections)
        educations = resume_ext.extract_education(resume.raw_text)
        # persist candidate profile + evidence (idempotent-ish: clear old rows for resume)
        for model, rid_field in ((CandidateSkill, "resume_id"),):
            pass
        prof = (await session.execute(select(CandidateProfile).where(CandidateProfile.resume_id == resume.id))).scalars().first()
        if prof is None:
            session.add(CandidateProfile(resume_id=resume.id, name=profile["name"][:255],
                                         email=profile["email"][:255], phone=profile["phone"][:64],
                                         location=profile["location"][:255], linkedin=profile["linkedin"][:512],
                                         github=profile["github"][:512]))
        for s in skills:
            ev = CandidateEvidence(resume_id=resume.id, text=s["source_text"][:2000],
                                   section=s["source_section"][:64], fact=s["fact"][:512],
                                   confidence=s["confidence"])
            session.add(ev)
            await session.flush()
            session.add(CandidateSkill(resume_id=resume.id, skill=s["fact"][:128],
                                       evidence_id=ev.id, confidence=s["confidence"]))
        for e in experiences:
            session.add(CandidateExperience(resume_id=resume.id, company=e["company"][:255],
                                            role=e["role"][:255], start_date=e["start_date"][:32],
                                            end_date=e["end_date"][:32], technologies=json.dumps(e["technologies"]),
                                            description=e["description"][:2000]))
        for e in educations:
            session.add(CandidateEducation(resume_id=resume.id, degree=e["degree"][:255],
                                           specialization=e.get("specialization", "")[:255],
                                           institution=e.get("institution", "")[:255], dates=e.get("dates", "")[:128]))
        timings["candidate_extraction_time"] = round(time.perf_counter() - t, 3)

        # --- requirement extraction ---
        t = time.perf_counter()
        requirements, tree = extract_requirements(job.raw_text, job.title)
        # LLM enrichment is best-effort and optional
        try:
            from app.nlp.llm.ollama import llm_parse_requirement
            for r in requirements[:5]:
                llm = await llm_parse_requirement(r["raw_text"])
                if llm and llm.canonical_skill:
                    r["confidence"] = max(r["confidence"], llm.confidence * 0.9)
        except Exception:
            pass
        # replace old requirements for job
        old = (await session.execute(select(JobRequirement).where(JobRequirement.job_id == job.id))).scalars().all()
        for o in old:
            await session.delete(o)
        for r in requirements:
            session.add(JobRequirement(job_id=job.id, raw_text=r["raw_text"][:2000],
                                       normalized_requirement=r["normalized_requirement"][:512],
                                       category=r["category"][:64], mandatory=r["mandatory"],
                                       preference=r["preference"][:32], operator=r["operator"][:16],
                                       minimum_years=r["minimum_years"], maximum_years=r["maximum_years"],
                                       confidence=r["confidence"], logic_group=(r["logic_group"] or "")[:64] if r["logic_group"] else None))
        session.add(RequirementGroup(job_id=job.id, operator="AND", expression=json.dumps(tree)))
        timings["requirement_extraction_time"] = round(time.perf_counter() - t, 3)
        await session.flush()
        analysis.progress = 55
        await session.commit()

        # reload persisted requirements to get ids
        req_rows = (await session.execute(select(JobRequirement).where(JobRequirement.job_id == job.id))).scalars().all()
        req_dicts = [{"id": r.id, "raw_text": r.raw_text, "normalized_requirement": r.normalized_requirement,
                      "category": r.category, "mandatory": r.mandatory, "preference": r.preference,
                      "operator": r.operator, "minimum_years": r.minimum_years,
                      "maximum_years": r.maximum_years, "confidence": r.confidence,
                      "logic_group": r.logic_group} for r in req_rows]

        # --- matching (deterministic base + optional RL decision layer) ---
        t = time.perf_counter()
        thresholds = {"transferable": settings.TRANSFERABLE_THRESHOLD, "semantic": settings.SEMANTIC_THRESHOLD}
        base_matches = [match_requirement(r, skills, experiences, resume.raw_text, thresholds) for r in req_dicts]
        matches = _maybe_apply_rl(req_dicts, base_matches, skills, experiences,
                                  resume.raw_text, thresholds, settings)
        timings["matching_time"] = round(time.perf_counter() - t, 3)

        for m in matches:
            session.add(RequirementMatch(analysis_id=analysis.id, requirement_id=m["requirement_id"],
                                         status=m["status"], confidence=m["confidence"],
                                         direct_match=m["direct_match"], transferable_match=m["transferable_match"],
                                         evidence=json.dumps(m["evidence"]), explanation=m["explanation"],
                                         estimated_years=m["estimated_years"],
                                         existing_status=m.get("existing_status"),
                                         rl_status=m.get("rl_status"),
                                         rl_confidence=m.get("rl_confidence"),
                                         rl_changed=bool(m.get("rl_changed_decision", False)),
                                         rl_used=bool(m.get("rl_used", False))))
        scores = compute_scores(matches, req_dicts, {
            "mandatory": settings.WEIGHT_MANDATORY, "preferred": settings.WEIGHT_PREFERRED,
            "experience": settings.WEIGHT_EXPERIENCE, "skill": settings.WEIGHT_SKILL,
            "transferability": settings.WEIGHT_TRANSFERABILITY, "confidence": settings.WEIGHT_CONFIDENCE})
        old_score = (await session.execute(select(AnalysisScore).where(AnalysisScore.analysis_id == analysis.id))).scalars().first()
        if old_score:
            await session.delete(old_score)
            await session.flush()
        session.add(AnalysisScore(analysis_id=analysis.id, overall=scores["overall"],
                                  mandatory_coverage=scores["mandatory_coverage"],
                                  preferred_coverage=scores["preferred_coverage"],
                                  experience_fit=scores["experience_fit"], skill_fit=scores["skill_fit"],
                                  transferability=scores["transferability"],
                                  evidence_confidence=scores["evidence_confidence"],
                                  eligibility=scores["eligibility"][:128],
                                  mandatory_total=scores["mandatory_total"],
                                  mandatory_satisfied=scores["mandatory_satisfied"],
                                  mandatory_partial=scores["mandatory_partial"],
                                  mandatory_missing=scores["mandatory_missing"]))
        timings["total_time"] = round(time.perf_counter() - t0, 3)
        analysis.status = "COMPLETED"; analysis.progress = 100
        analysis.timings = json.dumps(timings)
        await session.commit()
        logger.info(f"analysis {analysis_id} completed in {timings['total_time']}s")
    except Exception as e:  # never leak stack traces to UI; store short error
        logger.exception(f"analysis {analysis_id} failed: {e}")
        analysis.status = "FAILED"; analysis.error = str(e)[:1000]
        analysis.timings = json.dumps(timings)
        await session.commit()
