"""Unit tests for Resume Gap Analysis (derivation over stored match results).

The analyzer performs no matching of its own: tests run inputs through the
EXISTING pipeline (extract_requirements + match_requirement) and assert the
report is a faithful, non-fabricating reorganization of those results.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.nlp.extractors.requirements import extract_requirements
from app.nlp.extractors.resume import extract_skills, extract_experience
from app.nlp.matcher.engine import match_requirement
from app.nlp.parsers.documents import segment_sections
from app.nlp.gap.analyzer import build_gap_report
from app.nlp.ontology.skills import known_skills


def _pipeline(jd_text, resume_text):
    reqs, _ = extract_requirements(jd_text)
    secs = segment_sections(resume_text)
    skills = extract_skills(resume_text, secs)
    exps = extract_experience(resume_text, secs)
    matches = [match_requirement(r, skills, exps, resume_text) for r in reqs]
    return reqs, matches


def _req(norm, **kw):
    base = {"id": f"req_{norm[:20]}", "raw_text": norm, "normalized_requirement": norm,
            "category": "SKILL", "mandatory": True, "preference": "MANDATORY",
            "operator": "AND", "minimum_years": None, "maximum_years": None,
            "confidence": 0.9, "logic_group": None}
    base.update(kw)
    return base


def _skill(fact, section="Experience"):
    return {"fact": fact, "source_text": f"Worked with {fact} daily",
            "source_section": section, "confidence": 0.9}


def test_missing_skill_detection():
    reqs, matches = _pipeline("AWS required.", "Python backend developer.")
    report = build_gap_report(reqs, matches)
    assert report["summary"]["critical_gap_count"] >= 1
    gap = next(g for g in report["critical_gaps"] if g["normalized_requirement"] == "AWS")
    assert gap["status"] == "MISSING"
    assert gap["severity"] == "critical"
    assert gap["gap_category"] == "Missing Tools/Technologies"
    assert gap["evidence"] == []


def test_insufficient_experience():
    exps = [{"company": "Zoho", "role": "SWE", "start_date": "Jan 2024", "end_date": "Jan 2025",
             "technologies": ["Python"], "description": "Python APIs"}]
    r = _req("Python", minimum_years=3)
    m = match_requirement(r, [_skill("Python")], exps, "Python Jan 2024 Jan 2025")
    assert m["status"] == "PARTIALLY_SATISFIED"
    report = build_gap_report([r], [m])
    gap = report["critical_gaps"][0]
    assert gap["gap_category"] == "Insufficient Experience"
    assert "3" in gap["gap_explanation"] and "below" in gap["gap_explanation"]
    assert gap["required_years"] == 3 and gap["estimated_years"] is not None


def test_preferred_requirement_gaps():
    reqs, matches = _pipeline("Kubernetes preferred.", "Python backend developer.")
    report = build_gap_report(reqs, matches)
    assert report["summary"]["preferred_gap_count"] >= 1
    assert all(g["severity"] == "preferred" for g in report["preferred_gaps"])
    assert report["summary"]["critical_gap_count"] == 0


def test_mandatory_vs_preferred_separation():
    reqs, matches = _pipeline("AWS required. Kubernetes preferred.", "Python developer.")
    report = build_gap_report(reqs, matches)
    crit = {g["normalized_requirement"] for g in report["critical_gaps"]}
    pref = {g["normalized_requirement"] for g in report["preferred_gaps"]}
    assert "AWS" in crit and "Kubernetes" in pref
    assert not (crit & pref)


def test_transferable_skills():
    r = _req("PyTorch")
    m = match_requirement(r, [_skill("TensorFlow")], [], "TensorFlow deep learning")
    assert m["status"] == "TRANSFERABLE"
    report = build_gap_report([r], [m])
    assert len(report["transferable_skills"]) == 1
    t = report["transferable_skills"][0]
    assert t["transferable_sources"] and t["transferable_sources"][0]["skill"] == "TensorFlow"
    assert "does not demonstrate direct experience" in t["honesty_note"]
    # never converted into a possession claim
    assert "PyTorch experience" not in t["suggestion"].replace("used PyTorch", "")
    assert "Do not list PyTorch based only on related skills" in t["suggestion"]


def test_missing_evidence():
    r = _req("Kubernetes", minimum_years=3)
    m = match_requirement(r, [_skill("Kubernetes")], [],
                          "Worked on cloud deployments with Kubernetes")
    assert m["status"] == "INSUFFICIENT_EVIDENCE"
    report = build_gap_report([r], [m])
    assert len(report["insufficient_evidence"]) == 1
    assert report["insufficient_evidence"][0]["gap_category"] == "Missing Evidence"


def test_fully_satisfied_covered():
    r = _req("Python")
    m = match_requirement(r, [_skill("Python")], [], "Python backend work")
    report = build_gap_report([r], [m])
    assert len(report["covered_requirements"]) == 1
    assert report["summary"]["coverage_percentage"] == 100.0
    assert report["summary"]["critical_gap_count"] == 0


def test_contradictory_requirements():
    exps = [{"company": "X", "role": "SWE", "start_date": "Jan 2023", "end_date": "Jan 2024",
             "technologies": ["Python"], "description": "Python work"}]
    text = "Python developer with 10 years of experience. Software Engineer Jan 2023 - Jan 2024 Python work."
    r = _req("Python")
    m = match_requirement(r, [_skill("Python")], exps, text)
    assert m["status"] == "CONTRADICTORY"
    report = build_gap_report([r], [m])
    gap = report["critical_gaps"][0]
    assert gap["gap_category"] == "Contradictory Evidence"


def test_and_requirements():
    reqs, matches = _pipeline("Python and SQL required.", "Backend services using Python and FastAPI.")
    report = build_gap_report(reqs, matches)
    missing = {g["normalized_requirement"] for g in report["critical_gaps"]}
    covered = {c["normalized_requirement"] for c in report["covered_requirements"]}
    assert "SQL" in missing and "Python" in covered


def test_or_requirements():
    reqs, matches = _pipeline("Python or Java required.", "Backend services using Python and FastAPI.")
    report = build_gap_report(reqs, matches)
    assert report["summary"]["critical_gap_count"] == 0
    assert any(c.get("covered_by_or_group") for c in report["covered_requirements"])


def test_no_fabricated_recommendations():
    jd = "PyTorch required. 3+ years Machine Learning experience required. AWS required. Master's preferred."
    resume = "Built backend services using Python and FastAPI. TensorFlow models."
    reqs, matches = _pipeline(jd, resume)
    report = build_gap_report(reqs, matches)
    req_ids = {r["id"] for r in reqs}
    req_texts = " ".join((r.get("raw_text", "") + " " + r.get("normalized_requirement", "")).lower() for r in reqs)
    match_ev = {m["requirement_id"]: [e.get("text", "") for e in (m.get("evidence") or [])] for m in matches}
    skills = {s.lower() for s in known_skills()}
    for section in ("critical_gaps", "preferred_gaps", "transferable_skills", "insufficient_evidence"):
        for g in report[section]:
            # traceable to a real JD requirement
            assert g["requirement_id"] in req_ids
            # evidence copied verbatim from the stored match
            for e in g["evidence"]:
                assert e["text"] in match_ev[g["requirement_id"]]
            # suggestions name only skills present in the requirement text itself
            for token in g["suggestion"].split():
                clean = token.strip(".,;:()\"'").lower()
                if clean in skills:
                    assert clean in req_texts, f"fabricated skill in suggestion: {token}"
            # conditional wording only — never an assertion of possession
            assert g["suggestion"].startswith("If ") or "Review the stated" in g["suggestion"]


def test_resume_with_no_gaps():
    reqs, matches = _pipeline("Python required. SQL required.", "Python and SQL developer. Built APIs with Python and SQL.")
    report = build_gap_report(reqs, matches)
    assert report["summary"]["critical_gap_count"] == 0
    assert report["summary"]["preferred_gap_count"] == 0
    assert report["summary"]["coverage_percentage"] == 100.0
    assert "covers 2 of 2" in report["summary"]["overall_message"]


def test_resume_with_many_gaps():
    jd = "Python required. PyTorch required. 3+ years ML experience required. SQL required. Docker required. AWS required."
    reqs, matches = _pipeline(jd, "Java backend developer. Spring microservices.")
    report = build_gap_report(reqs, matches)
    total_gaps = report["summary"]["critical_gap_count"] + report["summary"]["preferred_gap_count"]
    assert total_gaps >= 4
    assert report["summary"]["coverage_percentage"] < 50.0
    assert report["honesty_note"]


def test_missing_education_gap():
    reqs, matches = _pipeline("Master's degree preferred.", "Bachelor's in Computer Science, VIT, 2020 - 2024.")
    report = build_gap_report(reqs, matches)
    assert report["summary"]["preferred_gap_count"] >= 1
    gap = report["preferred_gaps"][0]
    assert gap["gap_category"] == "Missing Education"
    assert "lower qualification" in gap["gap_explanation"]
    assert any("Bachelor" in e["text"] for e in gap["evidence"])
