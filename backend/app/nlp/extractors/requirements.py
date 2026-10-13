"""Job description -> atomic requirements with constraints (mandatory/preferred, AND/OR, thresholds)."""
from __future__ import annotations
import re
import uuid
from app.nlp.ontology.skills import normalize_skill, known_skills, skill_category, ALIASES

PREFERRED_CUES = re.compile(r"\b(preferred|prefer|nice to have|nice-to-have|bonus|plus|desired|ideal|optional)\b", re.I)
MANDATORY_CUES = re.compile(r"\b(required|requirement|must|mandatory|essential|necessary|minimum)\b", re.I)
YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", re.I)
EDU_RE = [
    (re.compile(r"\bph\.?\s*d\.?\b", re.I), "PhD", "EDUCATION"),
    (re.compile(r"\bmaster'?s?\b|\bm\.?\s*s\.?\b|\bmba\b|\bm\.?\s*tech\b", re.I), "Master's", "EDUCATION"),
    (re.compile(r"\bbachelor'?s?\b|\bb\.?\s*tech\b|\bb\.?\s*e\.?\b|\bbs\b|\bba\b", re.I), "Bachelor's", "EDUCATION"),
]


def segment_sentences(text: str) -> list[str]:
    """Sentence segmentation: try spaCy, fall back to deterministic regex splitter."""
    try:
        import spacy  # type: ignore

        try:
            nlp = spacy.load("en_core_web_sm")
            return [s.text.strip() for s in nlp(text).sents if s.text.strip()]
        except OSError:
            pass
    except ImportError:
        pass
    # deterministic fallback: split on bullets, newlines, sentence punctuation
    chunks = re.split(r"[\n•\-\*]+", text)
    out: list[str] = []
    for c in chunks:
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", c):
            s = s.strip(" -•\t")
            if len(s) >= 4:
                out.append(s)
    return out


def _find_skills(sentence: str) -> list[str]:
    found: list[str] = []
    alias_map: dict[str, str] = {k.lower(): v for k, v in ALIASES.items()}
    candidates = set(known_skills()) | {v for v in alias_map.values()}
    for skill in candidates:
        variants = {skill.lower()} | {a for a, c in alias_map.items() if c == skill}
        for v in variants:
            if re.search(r"(?<![A-Za-z0-9+#])" + re.escape(v) + r"(?![A-Za-z0-9+#])", sentence, re.I):
                found.append(normalize_skill(skill))
                break
    return sorted(set(found))


def _classify_preference(sentence: str, doc_has_requirements_header: bool = False) -> tuple[bool, str]:
    if PREFERRED_CUES.search(sentence):
        return (False, "PREFERRED")
    # default: requirements section => mandatory unless marked preferred
    return (True, "MANDATORY")


def extract_requirements(jd_text: str, title: str = "") -> tuple[list[dict], dict]:
    sentences = segment_sentences(jd_text)
    requirements: list[dict] = []
    or_groups: list[list[str]] = []
    for sent in sentences:
        skills = _find_skills(sent)
        years_m = YEARS_RE.search(sent)
        min_years = float(years_m.group(1)) if years_m else None
        mandatory, pref = _classify_preference(sent)
        has_or = bool(re.search(r"\bor\b", sent, re.I))
        operator = "OR" if (has_or and len(skills) > 1) else "AND"
        edu_hit = None
        for pat, label, cat in EDU_RE:
            if pat.search(sent):
                edu_hit = (label, cat)
                break
        if edu_hit and not skills:
            requirements.append({
                "id": f"req_{uuid.uuid4().hex[:8]}",
                "raw_text": sent,
                "normalized_requirement": edu_hit[0],
                "category": edu_hit[1],
                "mandatory": mandatory, "preference": pref, "operator": "AND",
                "minimum_years": None, "maximum_years": None,
                "time_window": None, "evidence_type": "EDUCATION",
                "confidence": 0.88, "logic_group": "education",
            })
            continue
        if not skills:
            # generic experience / domain requirement (e.g. "5 years software engineering")
            if years_m or re.search(r"\bexperience\b", sent, re.I):
                requirements.append({
                    "id": f"req_{uuid.uuid4().hex[:8]}",
                    "raw_text": sent,
                    "normalized_requirement": sent[:120],
                    "category": "EXPERIENCE",
                    "mandatory": mandatory, "preference": pref, "operator": "AND",
                    "minimum_years": min_years, "maximum_years": None,
                    "time_window": None, "evidence_type": "EXPERIENCE",
                    "confidence": 0.7, "logic_group": None,
                })
            continue
        if has_or and len(skills) > 1:
            gid = f"grp_{uuid.uuid4().hex[:8]}"
            for sk in skills:
                requirements.append({
                    "id": f"req_{uuid.uuid4().hex[:8]}",
                    "raw_text": sent,
                    "normalized_requirement": sk,
                    "category": skill_category(sk),
                    "mandatory": mandatory, "preference": pref, "operator": "OR",
                    "minimum_years": min_years, "maximum_years": None,
                    "time_window": None, "evidence_type": "EXPERIENCE",
                    "confidence": 0.9, "logic_group": gid,
                })
            or_groups.append([r["id"] for r in requirements[-len(skills):]])
        else:
            for sk in skills:
                requirements.append({
                    "id": f"req_{uuid.uuid4().hex[:8]}",
                    "raw_text": sent,
                    "normalized_requirement": sk,
                    "category": skill_category(sk),
                    "mandatory": mandatory, "preference": pref, "operator": "AND",
                    "minimum_years": min_years, "maximum_years": None,
                    "time_window": None, "evidence_type": "EXPERIENCE",
                    "confidence": 0.9, "logic_group": None,
                })
    tree = build_logic_tree(requirements)
    return requirements, tree


def build_logic_tree(requirements: list[dict]) -> dict:
    """Represent AND/OR structure as an expression tree."""
    groups: dict[str, list[dict]] = {}
    singles: list[dict] = []
    for r in requirements:
        if r.get("logic_group"):
            groups.setdefault(r["logic_group"], []).append(r)
        else:
            singles.append(r)
    children: list[dict] = []
    for r in singles:
        children.append({"requirement": r["normalized_requirement"], "requirement_id": r["id"],
                         "mandatory": r["mandatory"]})
    for gid, members in groups.items():
        children.append({"operator": "OR", "logic_group": gid,
                         "children": [{"requirement": m["normalized_requirement"],
                                       "requirement_id": m["id"], "mandatory": m["mandatory"]} for m in members]})
    return {"operator": "AND", "children": children}
