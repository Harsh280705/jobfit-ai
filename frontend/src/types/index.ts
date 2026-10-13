export type RequirementStatus =
  | 'FULLY_SATISFIED'
  | 'PARTIALLY_SATISFIED'
  | 'TRANSFERABLE'
  | 'MISSING'
  | 'INSUFFICIENT_EVIDENCE'
  | 'CONTRADICTORY';

export interface Evidence {
  text: string;
  section?: string;
  source?: string;
  confidence?: number;
  relation?: string;
  strength?: number;
}

export interface Requirement {
  id: string;
  raw_text: string;
  normalized_requirement: string;
  category: string;
  mandatory: boolean;
  preference: string;
  operator: string;
  minimum_years: number | null;
  confidence: number;
  /** Present in GET /analyses/{id} payloads; absent elsewhere. */
  logic_group?: string | null;
}

export interface Match {
  requirement_id: string;
  status: RequirementStatus;
  confidence: number;
  direct_match: boolean;
  transferable_match: boolean;
  evidence: Evidence[];
  explanation: string;
  estimated_years?: number | null;
  /** RL decision trace (additive; absent on pre-RL rows). */
  existing_status?: RequirementStatus;
  rl_status?: RequirementStatus | null;
  final_status?: RequirementStatus;
  rl_confidence?: number | null;
  rl_changed_decision?: boolean;
  rl_used?: boolean;
}

export interface Score {
  overall: number;
  mandatory_coverage: number;
  preferred_coverage: number;
  experience_fit: number;
  skill_fit: number;
  transferability: number;
  evidence_confidence: number;
  eligibility: string;
  mandatory_total: number;
  mandatory_satisfied: number;
  mandatory_partial: number;
  mandatory_missing: number;
}

export interface AnalysisDetail {
  id: string;
  status: string;
  progress: number;
  error: string;
  timings: Record<string, number>;
  score: Score | null;
  requirements: Requirement[];
  matches: Match[];
}

/** Row shape returned by GET /analyses (summary list). */
export interface AnalysisSummary {
  id: string;
  status: string;
  progress: number;
  overall: number | null;
  created_at: string | null;
  resume_id: string;
  job_id: string;
}

export interface EvaluationMethodMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  false_positive_rate: number;
  false_negative_rate: number;
}

export interface EvaluationResponse {
  dataset: string;
  n_cases: number;
  results: Record<string, EvaluationMethodMetrics>;
  /** Present when the backend compared the RL-enhanced matcher. */
  ablation?: {
    n_cases: number;
    n_changed: number;
    n_changed_correct: number;
    n_changed_incorrect: number;
    base_false_positives: number;
    rl_false_positives: number;
    base_false_negatives: number;
    rl_false_negatives: number;
  };
  fine_grained?: Record<string, Record<string, number | null>>;
  rl?: { used: boolean };
}

export interface RequirementDetailResponse {
  requirement: {
    id: string;
    raw_text: string;
    normalized_requirement: string;
    category: string;
    mandatory: boolean;
    minimum_years: number | null;
  };
  match: {
    status: RequirementStatus;
    confidence: number;
    evidence: Evidence[];
    explanation: string;
    estimated_years?: number | null;
    existing_status?: RequirementStatus;
    rl_status?: RequirementStatus | null;
    final_status?: RequirementStatus;
    rl_confidence?: number | null;
    rl_changed_decision?: boolean;
    rl_used?: boolean;
  } | null;
}

export const STATUS_LABEL: Record<RequirementStatus, { label: string; classes: string }> = {
  FULLY_SATISFIED: { label: '✅ Fully Satisfied', classes: 'bg-green-100 text-green-800' },
  PARTIALLY_SATISFIED: { label: '🟡 Partially Satisfied', classes: 'bg-yellow-100 text-yellow-800' },
  TRANSFERABLE: { label: '🔄 Transferable', classes: 'bg-blue-100 text-blue-800' },
  MISSING: { label: '❌ Missing', classes: 'bg-red-100 text-red-800' },
  INSUFFICIENT_EVIDENCE: { label: '⚠️ Insufficient Evidence', classes: 'bg-orange-100 text-orange-800' },
  CONTRADICTORY: { label: '🚨 Contradictory', classes: 'bg-purple-100 text-purple-800' },
};

export interface GapEvidence {
  text: string;
  section?: string;
  confidence?: number | null;
}

export interface GapItem {
  requirement_id: string;
  requirement_text: string;
  normalized_requirement: string;
  requirement_type: string;
  mandatory: boolean;
  severity: 'critical' | 'preferred';
  status: RequirementStatus;
  gap_category: string;
  evidence: GapEvidence[];
  evidence_confidence?: number | null;
  gap_explanation: string;
  suggestion: string;
  required_years?: number | null;
  estimated_years?: number | null;
  transferable_sources?: { skill: string; relation: string; strength?: number | null; evidence_text: string }[];
  honesty_note?: string;
  listed_as?: string;
  covered_by_or_group?: boolean;
}

export interface GapSummary {
  total_requirements: number;
  covered_count: number;
  critical_gap_count: number;
  preferred_gap_count: number;
  transferable_count: number;
  insufficient_evidence_count: number;
  coverage_percentage: number;
  overall_message: string;
}

export interface GapAnalysisResponse {
  analysis_id: string;
  critical_gaps: GapItem[];
  preferred_gaps: GapItem[];
  transferable_skills: GapItem[];
  insufficient_evidence: GapItem[];
  covered_requirements: (GapItem & { covered_by_or_group?: boolean })[];
  honesty_note: string;
  summary: GapSummary;
}
