"""Unit tests for critical matching logic (spec section 44-45). No heavy models required."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.nlp.ontology.skills import normalize_skill, transfer_strength
from app.nlp.extractors.requirements import extract_requirements, build_logic_tree
from app.nlp.matcher.experience import estimate_skill_years, detect_contradiction, merge_intervals
from app.nlp.matcher.engine import match_requirement
from app.nlp.matcher.scoring import compute_scores
from app.nlp.parsers.documents import TextParser, segment_sections


def _req(norm, **kw):
    base = {"id": "req_test", "raw_text": norm, "normalized_requirement": norm,
            "category": "SKILL", "mandatory": True, "preference": "MANDATORY",
            "operator": "AND", "minimum_years": None, "maximum_years": None,
            "confidence": 0.9, "logic_group": None}
    base.update(kw)
    return base


def _skill(fact, section="Experience"):
    return {"fact": fact, "source_text": f"Worked with {fact} daily", "source_section": section, "confidence": 0.9}


# Test 1: Python present directly -> FULLY_SATISFIED
def test_direct_match():
    m = match_requirement(_req("Python"), [_skill("Python")], [], "Python backend work")
    assert m["status"] == "FULLY_SATISFIED"


# Test 2: Python absent -> MISSING
def test_missing():
    m = match_requirement(_req("Python"), [_skill("Java")], [], "Java Spring work")
    assert m["status"] == "MISSING"


# Test 3: 1yr vs 3 required -> PARTIALLY_SATISFIED
def test_partial_experience():
    exps = [{"company": "Zoho", "role": "SWE", "start_date": "Jan 2024", "end_date": "Present",
             "technologies": ["Python"], "description": "Python APIs"}]
    # freeze "Present" by using explicit end date range instead
    exps[0]["end_date"] = "Jan 2025"
    m = match_requirement(_req("Python", minimum_years=3), [_skill("Python")], exps, "Python Jan 2024 Jan 2025")
    assert m["status"] == "PARTIALLY_SATISFIED"


# Test 4: PyTorch required, TensorFlow present -> TRANSFERABLE
def test_transferable():
    m = match_requirement(_req("PyTorch"), [_skill("TensorFlow")], [], "TensorFlow deep learning")
    assert m["status"] == "TRANSFERABLE"


def test_alias_normalization():
    assert normalize_skill("Postgres") == "PostgreSQL"
    assert normalize_skill("K8s") == "Kubernetes"
    assert normalize_skill("JS") == "JavaScript"
    rel, strength = transfer_strength("PyTorch", "TensorFlow")
    assert rel == "TRANSFERABLE" and strength >= 0.8
    # weak relation must NOT be declared transferable-strong
    rel2, s2 = transfer_strength("Java", "Python")
    assert s2 < 0.55 or rel2 in (None, "RELATED")


def test_and_or_logic():
    reqs, tree = extract_requirements("Experience with PyTorch or TensorFlow preferred. Python and SQL required.")
    ors = [r for r in reqs if r["operator"] == "OR"]
    assert len(ors) >= 2  # PyTorch OR TensorFlow
    assert tree["operator"] == "AND"
    assert any(c.get("operator") == "OR" for c in tree["children"])


def test_experience_no_double_count():
    ivs = [((2022, 1), (2023, 1)), ((2022, 6), (2023, 6))]
    merged = merge_intervals(ivs)
    assert len(merged) == 1  # overlapping merged


# Test 7: missing dates -> INSUFFICIENT_EVIDENCE
def test_insufficient_evidence():
    m = match_requirement(_req("Kubernetes", minimum_years=3), [_skill("Kubernetes")], [],
                          "Worked on cloud deployments with Kubernetes")
    assert m["status"] == "INSUFFICIENT_EVIDENCE"


# Test 8: contradictory
def test_contradictory():
    exps = [{"company": "X", "role": "SWE", "start_date": "Jan 2023", "end_date": "Jan 2024",
             "technologies": ["Python"], "description": "Python work"}]
    text = "Python developer with 10 years of experience. Software Engineer Jan 2023 - Jan 2024 Python work."
    c = detect_contradiction("Python", exps, text)
    assert c is not None
    m = match_requirement(_req("Python"), [_skill("Python")], exps, text)
    assert m["status"] == "CONTRADICTORY"


def test_mandatory_gate_caps_score():
    reqs = [_req("Python"), _req("SQL")]
    matches = [
        {"requirement_id": "req_test", "status": "FULLY_SATISFIED", "confidence": 0.9, "direct_match": True, "transferable_match": False},
        {"requirement_id": "req_test", "status": "MISSING", "confidence": 0.85, "direct_match": False, "transferable_match": False},
    ]
    # map both matches onto distinct requirements
    r1 = dict(reqs[0], id="a")
    r2 = dict(reqs[1], id="b")
    matches[0]["requirement_id"] = "a"
    matches[1]["requirement_id"] = "b"
    scores = compute_scores(matches, [r1, r2])
    assert scores["overall"] <= 59
    assert "NOT ELIGIBLE" in scores["eligibility"]


def test_text_parser_and_sections():
    parsed = TextParser().parse(b"Skills\nPython, SQL\n\nExperience\nBuilt APIs", "r.txt")
    assert "Python" in parsed["text"]
    secs = segment_sections("Skills\nPython\nExperience\nBuilt APIs with Python")
    assert any(s["name"] == "Skills" for s in secs)
