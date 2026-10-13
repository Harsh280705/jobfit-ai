"""Experience engine: date-interval merging without double counting + claim-vs-timeline contradiction."""
from __future__ import annotations
import re
from datetime import datetime

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def parse_date(s: str) -> tuple[int, int] | None:
    s = (s or "").strip()
    if not s:
        return None
    if s.lower() in ("present", "now", "current"):
        now = datetime.utcnow()
        return (now.year, now.month)
    m = re.match(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})", s, re.I)
    if m:
        return (int(m.group(2)), MONTHS[m.group(1).lower()[:3]])
    m = re.match(r"(\d{4})(?:/(\d{1,2}))?", s)
    if m:
        return (int(m.group(1)), int(m.group(2) or 1))
    m = re.match(r"(\d{1,2})/(\d{4})", s)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    return None


def months_between(start: tuple[int, int], end: tuple[int, int]) -> int:
    return max(0, (end[0] - start[0]) * 12 + (end[1] - start[1]))


def merge_intervals(intervals: list[tuple[tuple[int, int], tuple[int, int]]]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if not intervals:
        return []
    key = lambda iv: (iv[0][0], iv[0][1])
    ivs = sorted(intervals, key=key)
    merged = [ivs[0]]
    for s, e in ivs[1:]:
        ls, le = merged[-1]
        if (s[0], s[1]) <= (le[0], le[1]):
            if (e[0], e[1]) > (le[0], le[1]):
                merged[-1] = (ls, e)
        else:
            merged.append((s, e))
    return merged


def estimate_skill_years(skill: str, experiences: list[dict], resume_text: str = "") -> dict:
    """Estimate years of `skill` from dated positions mentioning it. Never fabricate when dates missing."""
    from app.nlp.ontology.skills import normalize_skill
    target = normalize_skill(skill)
    intervals: list[tuple[tuple[int, int], tuple[int, int]]] = []
    evidence: list[str] = []
    dated = 0
    undated_mentions = 0
    for exp in experiences:
        techs = [normalize_skill(t) for t in (exp.get("technologies") or [])]
        blob = (exp.get("description", "") + " " + exp.get("role", "")).lower()
        mentions = (target.lower() in [t.lower() for t in techs]) or (target.lower() in blob)
        if not mentions:
            continue
        s = parse_date(exp.get("start_date", ""))
        e = parse_date(exp.get("end_date", ""))
        if s and e:
            intervals.append((s, e))
            dated += 1
            evidence.append(f"{exp.get('role','')} at {exp.get('company','')}, {exp.get('start_date','')}–{exp.get('end_date','')}")
        else:
            undated_mentions += 1
    if not intervals:
        return {"skill": target, "estimated_years": None, "confidence": 0.3,
                "evidence": evidence, "note": "no dated evidence",
                "undated_mentions": undated_mentions}
    merged = merge_intervals(intervals)
    months = sum(months_between(s, e) for s, e in merged)
    years = round(months / 12, 2)
    conf = 0.9 if dated >= 2 else 0.75
    if undated_mentions:
        conf = max(0.5, conf - 0.1)
    return {"skill": target, "estimated_years": years, "confidence": conf,
            "evidence": evidence, "note": "", "undated_mentions": undated_mentions}


def detect_contradiction(skill: str, experiences: list[dict], resume_text: str) -> dict | None:
    """Flag when an explicit 'N years of X' claim exceeds timeline-backed evidence by a wide margin."""
    from app.nlp.ontology.skills import normalize_skill
    target = normalize_skill(skill).lower()
    claims: list[float] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)[^.\n]{0,60}", resume_text, re.I):
        ctx = m.group(0).lower()
        window = resume_text[max(0, m.start()-80):m.end()+80].lower()
        if target in ctx or target in window:
            try:
                claims.append(float(m.group(1)))
            except ValueError:
                pass
    if not claims:
        return None
    est = estimate_skill_years(skill, experiences, resume_text)
    if est["estimated_years"] is None:
        return None
    claimed = max(claims)
    if claimed >= est["estimated_years"] + 2.0 and claimed >= 3:
        return {"claimed_years": claimed, "timeline_years": est["estimated_years"],
                "explanation": f"Resume claims ~{claimed} years of {skill} but dated roles support ~{est['estimated_years']} years."}
    return None
