"""Rebuild skill ontology artifacts (validates relationships + writes data/skill_ontology.json)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.nlp.ontology.skills import ALIASES, CANONICAL, RELATIONSHIPS

out = {"canonical": CANONICAL, "aliases": ALIASES,
       "relationships": [{"a": a, "b": b, "type": r, "strength": s} for a, b, r, s in RELATIONSHIPS]}
dest = os.path.join(os.path.dirname(__file__), "..", "data", "skill_ontology.json")
with open(dest, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print(f"wrote {dest} ({len(CANONICAL)} skills, {len(ALIASES)} aliases, {len(RELATIONSHIPS)} relationships)")
