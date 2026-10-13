"""SQLAlchemy 2.x models. UUID PKs, timestamps, FK constraints, indexes."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_type: Mapped[str] = mapped_column(String(32), index=True)  # resume | job_description
    filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    storage_path: Mapped[str] = mapped_column(String(1024))
    text_content: Mapped[str] = mapped_column(Text, default="")


class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    document: Mapped[Document] = relationship(lazy="joined")


class JobDescription(Base, TimestampMixin):
    __tablename__ = "job_descriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(512), default="Untitled role")
    raw_text: Mapped[str] = mapped_column(Text, default="")


class CandidateProfile(Base, TimestampMixin):
    __tablename__ = "candidate_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    linkedin: Mapped[str] = mapped_column(String(512), default="")
    github: Mapped[str] = mapped_column(String(512), default="")


class CandidateEvidence(Base, TimestampMixin):
    __tablename__ = "candidate_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(String(64), default="Other")
    fact: Mapped[str] = mapped_column(String(512), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)


class CandidateExperience(Base, TimestampMixin):
    __tablename__ = "candidate_experience"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(255), default="")
    start_date: Mapped[str] = mapped_column(String(32), default="")
    end_date: Mapped[str] = mapped_column(String(32), default="")
    duration_years: Mapped[float] = mapped_column(Float, default=0.0)
    technologies: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    description: Mapped[str] = mapped_column(Text, default="")


class CandidateEducation(Base, TimestampMixin):
    __tablename__ = "candidate_education"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    degree: Mapped[str] = mapped_column(String(255), default="")
    specialization: Mapped[str] = mapped_column(String(255), default="")
    institution: Mapped[str] = mapped_column(String(255), default="")
    dates: Mapped[str] = mapped_column(String(128), default="")


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    canonical_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(64), default="OTHER")
    description: Mapped[str] = mapped_column(Text, default="")


class SkillAlias(Base, TimestampMixin):
    __tablename__ = "skill_aliases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    alias: Mapped[str] = mapped_column(String(128), index=True)
    canonical_name: Mapped[str] = mapped_column(String(128), index=True)


class SkillRelationship(Base, TimestampMixin):
    __tablename__ = "skill_relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    skill_a: Mapped[str] = mapped_column(String(128), index=True)
    skill_b: Mapped[str] = mapped_column(String(128), index=True)
    relation_type: Mapped[str] = mapped_column(String(32), default="RELATED")  # ALIAS|SAME_FAMILY|RELATED|TRANSFERABLE|...
    strength: Mapped[float] = mapped_column(Float, default=0.5)


class CandidateSkill(Base, TimestampMixin):
    __tablename__ = "candidate_skills"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(128), index=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("candidate_evidence.id", ondelete="SET NULL"), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)


class JobRequirement(Base, TimestampMixin):
    __tablename__ = "job_requirements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_requirement: Mapped[str] = mapped_column(String(512), default="")
    category: Mapped[str] = mapped_column(String(64), default="OTHER")
    mandatory: Mapped[bool] = mapped_column(default=True)
    preference: Mapped[str] = mapped_column(String(32), default="MANDATORY")
    operator: Mapped[str] = mapped_column(String(16), default="AND")
    minimum_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    maximum_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    logic_group: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RequirementGroup(Base, TimestampMixin):
    __tablename__ = "requirement_groups"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"), index=True)
    operator: Mapped[str] = mapped_column(String(16), default="AND")
    expression: Mapped[str] = mapped_column(Text, default="{}")  # JSON expression tree


class Analysis(Base, TimestampMixin):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    timings: Mapped[str] = mapped_column(Text, default="{}")


class RequirementMatch(Base, TimestampMixin):
    __tablename__ = "requirement_matches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey("job_requirements.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    direct_match: Mapped[bool] = mapped_column(default=False)
    transferable_match: Mapped[bool] = mapped_column(default=False)
    evidence: Mapped[str] = mapped_column(Text, default="[]")
    explanation: Mapped[str] = mapped_column(Text, default="")
    estimated_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    # RL decision trace (nullable/additive: old rows and old consumers unaffected).
    existing_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rl_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rl_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rl_changed: Mapped[bool] = mapped_column(default=False)
    rl_used: Mapped[bool] = mapped_column(default=False)


class AnalysisScore(Base, TimestampMixin):
    __tablename__ = "analysis_scores"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), unique=True, index=True)
    overall: Mapped[float] = mapped_column(Float, default=0.0)
    mandatory_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    preferred_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    experience_fit: Mapped[float] = mapped_column(Float, default=0.0)
    skill_fit: Mapped[float] = mapped_column(Float, default=0.0)
    transferability: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    eligibility: Mapped[str] = mapped_column(String(128), default="")
    mandatory_total: Mapped[int] = mapped_column(Integer, default=0)
    mandatory_satisfied: Mapped[int] = mapped_column(Integer, default=0)
    mandatory_partial: Mapped[int] = mapped_column(Integer, default=0)
    mandatory_missing: Mapped[int] = mapped_column(Integer, default=0)


class Embedding(Base, TimestampMixin):
    __tablename__ = "embeddings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_type: Mapped[str] = mapped_column(String(32), index=True)  # skill | requirement | evidence
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    vector: Mapped[str] = mapped_column(Text, default="[]")  # JSON list; pgvector in prod migration


class EvaluationDataset(Base, TimestampMixin):
    __tablename__ = "evaluation_datasets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")


class EvaluationCase(Base, TimestampMixin):
    __tablename__ = "evaluation_cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), index=True)
    requirement_text: Mapped[str] = mapped_column(Text)
    resume_text: Mapped[str] = mapped_column(Text)
    expected_status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="general")


class AnalysisJob(Base, TimestampMixin):
    __tablename__ = "analysis_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    celery_task_id: Mapped[str] = mapped_column(String(128), default="")
    state: Mapped[str] = mapped_column(String(32), default="QUEUED")
