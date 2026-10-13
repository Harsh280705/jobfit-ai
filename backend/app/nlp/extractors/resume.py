"""Resume information extraction with evidence spans (rule-based + optional spaCy)."""
from __future__ import annotations
import re
from app.nlp.ontology.skills import normalize_skill, known_skills, ALIASES

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
LINKEDIN_RE = re.compile(r"(https?://)?(www\.)?linkedin\.com/\S+", re.I)
GITHUB_RE = re.compile(r"(https?://)?(www\.)?github\.com/\S+", re.I)
DATE_RANGE_RE = re.compile(
    r"(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|\d{4}(?:/\d{1,2})?|\d{1,2}/\d{4})"
    r"\s*(?:[-–—]|to)\s*"
    r"(?P<end>Present|present|Now|now|Current|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|\d{4}(?:/\d{1,2})?|\d{1,2}/\d{4})"
)
YEARS_CLAIM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience\s+)?(?:in|with|using)?\s*([A-Za-z][A-Za-z0-9+#./\- ]{1,40})?", re.I)

DEGREE_PATTERNS = [
    (re.compile(r"\b(ph\.?\s*d\.?|doctorate)\b", re.I), "PhD"),
    (re.compile(r"\b(m\.?\s*tech|master of technology)\b", re.I), "M.Tech"),
    (re.compile(r"\b(m\.?\s*s\.?|m\.?\s*sc\.?|master of science|master'?s)\b", re.I), "Master's"),
    (re.compile(r"\bmba\b", re.I), "MBA"),
    (re.compile(r"\b(b\.?\s*tech|bachelor of technology)\b", re.I), "B.Tech"),
    (re.compile(r"\b(b\.?\s*e\.?|bachelor of engineering)\b", re.I), "B.E."),
    (re.compile(r"\b(b\.?\s*s\.?|b\.?\s*sc\.?|bachelor'?s)\b", re.I), "Bachelor's"),
]


def extract_profile(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    name = lines[0] if lines else ""
    if len(name) > 60 or "@" in name:
        name = ""
    return {
        "name": name,
        "email": (EMAIL_RE.search(text).group(0) if EMAIL_RE.search(text) else ""),
        "phone": (PHONE_RE.search(text).group(0).strip() if PHONE_RE.search(text) else ""),
        "location": _guess_location(text),
        "linkedin": (LINKEDIN_RE.search(text).group(0) if LINKEDIN_RE.search(text) else ""),
        "github": (GITHUB_RE.search(text).group(0) if GITHUB_RE.search(text) else ""),
    }


def _guess_location(text: str) -> str:
    m = re.search(r"(?:Location|Based in|located in)\s*:?\s*([A-Za-z][A-Za-z ,\-]{2,60})", text, re.I)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?),\s*([A-Z]{2}|[A-Z][a-z]+)\b", text)
    return m2.group(0) if m2 else ""


def extract_skills(text: str, sections: list[dict]) -> list[dict]:
    """Skill mention extraction preserving source spans."""
    found: list[dict] = []
    seen: set[str] = set()
    skills = known_skills()
    alias_map = {k.lower(): v for k, v in ALIASES.items()}
    for sec in sections:
        sec_text = sec.get("text", "")
        sec_name = sec.get("name", "Other")
        low = sec_text.lower()
        for skill in skills:
            for variant in {skill.lower(), *[a for a, c in alias_map.items() if c == skill]}:
                pat = re.compile(r"(?<![A-Za-z0-9+#])" + re.escape(variant) + r"(?![A-Za-z0-9+#])", re.I)
                for m in pat.finditer(sec_text):
                    canon = normalize_skill(skill)
                    if (canon, sec_name) in seen:
                        continue
                    seen.add((canon, sec_name))
                    start = max(0, m.start() - 60)
                    end = min(len(sec_text), m.end() + 60)
                    found.append({
                        "fact": canon,
                        "source_text": sec_text[start:end].strip(),
                        "source_section": sec_name,
                        "confidence": 0.94 if sec_name in ("Skills", "Experience") else 0.85,
                    })
                    break
    # full-text fallback if no sections matched
    if not found:
        for skill in skills:
            if re.search(r"(?<![A-Za-z0-9+#])" + re.escape(skill) + r"(?![A-Za-z0-9+#])", text, re.I):
                m = re.search(r"(?<![A-Za-z0-9+#])" + re.escape(skill) + r"(?![A-Za-z0-9+#])", text, re.I)
                assert m
                found.append({"fact": skill, "source_text": text[max(0, m.start()-60):m.end()+60],
                              "source_section": "Other", "confidence": 0.7})
    return found


def extract_experience(text: str, sections: list[dict]) -> list[dict]:
    exp_sections = [s for s in sections if s.get("name", "").lower() in ("experience", "work experience", "employment")]
    blob = "\n".join([s.get("text", "") for s in exp_sections]) if exp_sections else text
    # split into blocks on blank lines or date ranges
    blocks = [b.strip() for b in re.split(r"\n\s*\n", blob) if b.strip()]
    out = []
    for b in blocks[:20]:
        m = DATE_RANGE_RE.search(b)
        first_line = b.splitlines()[0] if b.splitlines() else b[:80]
        # role/company heuristic: "Role at Company" or "Role, Company" or "Role - Company"
        role, company = first_line[:120], ""
        for sep in [" at ", " @ ", " - ", " | ", ", "]:
            if sep in first_line:
                parts = first_line.split(sep)
                role, company = parts[0].strip()[:120], parts[1].strip()[:120]
                break
        techs = [e["fact"] for e in extract_skills(b, [{"name": "Experience", "text": b}])]
        out.append({
            "company": company, "role": role,
            "start_date": (m.group("start") if m else ""),
            "end_date": (m.group("end") if m else ""),
            "technologies": techs,
            "description": b[:2000],
        })
    return out


def extract_education(text: str) -> list[dict]:
    out = []
    for pat, label in DEGREE_PATTERNS:
        for m in pat.finditer(text):
            ctx = text[max(0, m.start()-120):m.end()+120]
            inst = ""
            im = re.search(r"(University|Institute|College|IIT|NIT|School)[A-Za-z ,&\-]*", ctx)
            if im:
                inst = im.group(0).strip()[:120]
            out.append({"degree": label, "specialization": _guess_spec(ctx),
                        "institution": inst, "dates": _guess_dates(ctx)})
            break
    return out


def _guess_spec(ctx: str) -> str:
    m = re.search(r"(Computer Science|Information Technology|Data Science|Electrical|Electronics|Mechanical|Business|MBA|AI|Artificial Intelligence|Machine Learning)", ctx, re.I)
    return m.group(1) if m else ""


def _guess_dates(ctx: str) -> str:
    m = re.search(r"(19|20)\d{2}\s*[-–]\s*((19|20)\d{2}|Present|present)", ctx)
    return m.group(0) if m else ""


def extract_certifications(text: str) -> list[dict]:
    certs = []
    for m in re.finditer(r"\b(AWS|Azure|GCP|PMP|CKA|TensorFlow|Google|Microsoft|Oracle|Cisco)\b[^.\n]{0,80}?(certified|certification|certificate|associate|professional)", text, re.I):
        certs.append({"certification": m.group(0).strip()[:200], "issuer": m.group(1), "date": _guess_dates(m.group(0))})
    return certs[:20]


def extract_projects(text: str, sections: list[dict]) -> list[dict]:
    proj = [s for s in sections if s.get("name", "").lower() == "projects"]
    blob = "\n".join([s.get("text", "") for s in proj])
    if not blob:
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", blob) if b.strip()][:10]
    return [{"project_name": b.splitlines()[0][:120] if b.splitlines() else b[:120],
             "technologies": [e["fact"] for e in extract_skills(b, [{"name": "Projects", "text": b}])],
             "description": b[:1500]} for b in blocks]
