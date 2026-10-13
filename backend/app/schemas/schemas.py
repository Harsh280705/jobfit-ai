"""Pydantic v2 API schemas."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

RequirementStatus = Literal[
    "FULLY_SATISFIED", "PARTIALLY_SATISFIED", "TRANSFERABLE",
    "MISSING", "INSUFFICIENT_EVIDENCE", "CONTRADICTORY",
]
AnalysisState = Literal["QUEUED", "PROCESSING", "COMPLETED", "FAILED"]


class DocumentOut(BaseModel):
    id: str
    document_type: str
    filename: str
    mime_type: str


class ResumeCreate(BaseModel):
    document_id: str | None = None
    text: str | None = None


class ResumeOut(BaseModel):
    id: str
    raw_text: str = ""


class JobCreate(BaseModel):
    document_id: str | None = None
    title: str = "Untitled role"
    text: str | None = None


class JobOut(BaseModel):
    id: str
    title: str
    raw_text: str = ""


class AnalysisCreate(BaseModel):
    resume_id: str
    job_description_id: str = Field(alias="job_id", default=None)  # accept both
    job_id: str | None = None

    def resolved_job_id(self) -> str:
        return self.job_id or self.job_description_id or ""


class AnalysisOut(BaseModel):
    analysis_id: str
    status: str
    progress: int = 0


class AnalysisDetail(BaseModel):
    id: str
    status: str
    progress: int = 0
    error: str = ""
    timings: dict[str, Any] = {}
    score: dict[str, Any] | None = None
    matches: list[dict[str, Any]] = []
    requirements: list[dict[str, Any]] = []


class EvidenceItem(BaseModel):
    text: str
    section: str = "Other"
    source: str = "resume"
    confidence: float = 0.8


class MatchOut(BaseModel):
    requirement_id: str
    status: str
    confidence: float
    direct_match: bool
    transferable_match: bool
    evidence: list[dict[str, Any]]
    explanation: str
    estimated_years: float | None = None


class EvaluationRunRequest(BaseModel):
    dataset: str = "seed"
    include_semantic: bool = True


class GapEvidenceOut(BaseModel):
    text: str = ""
    section: str = "Other"
    confidence: float | None = None


class GapItemOut(BaseModel):
    requirement_id: str
    requirement_text: str = ""
    normalized_requirement: str = ""
    requirement_type: str = "OTHER"
    mandatory: bool = True
    severity: str = "critical"
    status: str = "MISSING"
    gap_category: str = "Missing Skills"
    evidence: list[GapEvidenceOut] = []
    evidence_confidence: float | None = None
    gap_explanation: str = ""
    suggestion: str = ""
    required_years: float | None = None
    estimated_years: float | None = None


class GapSummaryOut(BaseModel):
    total_requirements: int = 0
    covered_count: int = 0
    critical_gap_count: int = 0
    preferred_gap_count: int = 0
    transferable_count: int = 0
    insufficient_evidence_count: int = 0
    coverage_percentage: float = 0.0
    overall_message: str = ""


class GapAnalysisOut(BaseModel):
    analysis_id: str
    critical_gaps: list[dict[str, Any]] = []
    preferred_gaps: list[dict[str, Any]] = []
    transferable_skills: list[dict[str, Any]] = []
    insufficient_evidence: list[dict[str, Any]] = []
    covered_requirements: list[dict[str, Any]] = []
    honesty_note: str = ""
    summary: GapSummaryOut = GapSummaryOut()
