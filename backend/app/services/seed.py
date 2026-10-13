"""Seed canonical skills / aliases / relationships into the DB (idempotent)."""
from __future__ import annotations
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.models import Skill, SkillAlias, SkillRelationship
from app.nlp.ontology.skills import ALIASES, CANONICAL, RELATIONSHIPS


async def ensure_skill_seed() -> None:
    async with SessionLocal() as s:
        existing = (await s.execute(select(Skill))).scalars().all()
        if existing:
            return
        for canon, cat in CANONICAL.items():
            s.add(Skill(canonical_name=canon, category=cat))
        for alias, canon in ALIASES.items():
            s.add(SkillAlias(alias=alias, canonical_name=canon))
        for a, b, rel, strength in RELATIONSHIPS:
            s.add(SkillRelationship(skill_a=a, skill_b=b, relation_type=rel, strength=strength))
        await s.commit()
