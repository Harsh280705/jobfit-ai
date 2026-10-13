import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchGapAnalysis } from '../services/api';
import { StatusBadge } from './badges';
import { ListSkeleton } from './ui';
import type { GapAnalysisResponse, GapItem } from '../types';

/** Compact gap card: single status badge, tight hierarchy, collapsible secondary detail. */
function GapCard({ gap, accent }: { gap: GapItem; accent: 'red' | 'amber' | 'indigo' | 'slate' }) {
  const [open, setOpen] = useState(false);
  const accentBar =
    accent === 'red'
      ? 'border-l-red-500'
      : accent === 'amber'
        ? 'border-l-amber-500'
        : accent === 'indigo'
          ? 'border-l-indigo-500'
          : 'border-l-slate-500';
  const hasEvidence = gap.evidence.length > 0;
  const hasSources = (gap.transferable_sources?.length ?? 0) > 0;

  return (
    <article className={`ai-card border-l-4 ${accentBar} px-4 py-3`}>
      <div className="flex flex-wrap items-start gap-2">
        <div className="flex-1 min-w-[180px]">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-white">{gap.normalized_requirement}</h4>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {gap.mandatory ? 'Mandatory' : 'Preferred'}
            {gap.required_years ? ` · Requires ${gap.required_years}+ yrs` : ''}
            {gap.estimated_years !== undefined && gap.estimated_years !== null
              ? ` · Documented ~${gap.estimated_years} yrs` : ''}
          </p>
        </div>
        <StatusBadge status={gap.status} compact />
      </div>

      <p className="mt-2 text-[13px] text-slate-300 leading-5">{gap.gap_explanation}</p>

      {hasSources && (
        <div className="mt-2 rounded-lg bg-indigo-500/10 border border-indigo-400/30 px-3 py-2">
          <p className="text-xs font-semibold text-indigo-200">Related evidence — not direct experience</p>
          <p className="text-xs text-indigo-200/90 mt-0.5">
            Target: <strong>{gap.normalized_requirement}</strong>
            {' · Related: '}
            {gap.transferable_sources!
              .map((s) => `${s.skill}${s.strength ? ` (${s.relation}, ${s.strength})` : ''}`)
              .join('; ')}
          </p>
        </div>
      )}

      <div className="mt-2">
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="text-xs font-semibold text-indigo-300 hover:text-indigo-200 hover:underline rounded px-1 py-0.5 -ml-1"
        >
          {open ? 'Hide details ▴' : `Show evidence & suggestion ▾`}
        </button>
        {open && (
          <div className="mt-2 space-y-2">
            {hasEvidence ? (
              <div className="space-y-1.5">
                {gap.evidence.slice(0, 2).map((e, i) => (
                  <blockquote
                    key={i}
                    className="border-l-2 border-[#2a3a6e] bg-[#0a1230] rounded-r-md px-2.5 py-1.5 text-xs text-slate-300 leading-5"
                  >
                    “{e.text}”
                  </blockquote>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No resume evidence found — this reflects missing evidence, not proof the skill is absent.</p>
            )}
            <p className="text-xs text-slate-300 leading-5">
              <span className="font-semibold text-white">Suggestion: </span>
              {gap.suggestion}
            </p>
          </div>
        )}
      </div>
    </article>
  );
}

function GapGroup({
  title,
  description,
  items,
  emptyHint,
  accent,
  hideWhenEmpty = false,
}: {
  title: string;
  description?: string;
  items: GapItem[];
  emptyHint: string;
  accent: 'red' | 'amber' | 'indigo' | 'slate';
  hideWhenEmpty?: boolean;
}) {
  if (items.length === 0 && hideWhenEmpty) return null;
  return (
    <div className="ai-card p-4">
      <div className="flex items-baseline gap-2 mb-1">
        <h3 className="text-sm font-bold text-white tracking-tight tabular-nums">
          {title} <span className="text-slate-500 font-semibold">({items.length})</span>
        </h3>
      </div>
      {description && <p className="text-xs text-slate-400 mb-3 leading-5">{description}</p>}
      {items.length === 0 ? (
        <p className="text-[13px] text-slate-500 italic rounded-lg border border-dashed border-[#2a3a6e] bg-[#0a1230] px-3 py-2.5">{emptyHint}</p>
      ) : (
        <div className="grid gap-3 xl:grid-cols-2">
          {items.map((g) => (
            <GapCard key={g.requirement_id} gap={g} accent={accent} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Resume Gap Analysis section: derived strictly from stored match results. */
export function GapAnalysisSection({ analysisId }: { analysisId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['gap-analysis', analysisId],
    queryFn: () => fetchGapAnalysis(analysisId),
    enabled: !!analysisId,
    retry: false,
  });

  if (isLoading) {
    return (
      <section aria-label="Resume gap analysis" className="space-y-3">
        <div className="ai-rule">
          <h2 className="text-lg font-bold text-white tracking-tight">Resume gap analysis</h2>
        </div>
        <ListSkeleton rows={3} />
      </section>
    );
  }
  if (error || !data) return null;
  const report: GapAnalysisResponse = data;
  const s = report.summary;

  const stats: { label: string; value: number; classes: string }[] = [
    { label: 'Critical gaps', value: s.critical_gap_count, classes: 'bg-red-500/15 text-red-300 border-red-500/40' },
    { label: 'Preferred gaps', value: s.preferred_gap_count, classes: 'bg-amber-500/15 text-amber-300 border-amber-500/40' },
    { label: 'Transferable', value: s.transferable_count, classes: 'bg-indigo-500/15 text-indigo-200 border-indigo-400/40' },
    { label: 'Insufficient evidence', value: s.insufficient_evidence_count, classes: 'bg-white/5 text-slate-300 border-white/15' },
  ];

  return (
    <section aria-label="Resume gap analysis" className="space-y-5">
      <div className="ai-rule">
        <h2 className="text-lg font-bold text-white tracking-tight">Resume gap analysis</h2>
        <p className="text-xs text-slate-400 tabular-nums ml-auto hidden md:block">{s.overall_message}</p>
      </div>

      {/* Summary strip — real values only */}
      <div className="ai-card p-4 sm:p-5">
        <p className="text-sm font-semibold text-white">Requirement coverage</p>
        <p className="text-[13px] text-slate-300 leading-6 mt-1">
          Gaps are identified from the supplied job description and the evidence available in the resume.
          Missing evidence does not prove the candidate lacks a skill.
        </p>
        <div className="flex flex-wrap gap-1.5 mt-3" role="list" aria-label="Gap counts">
          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs bg-emerald-500/15 text-emerald-300 border-emerald-500/40" role="listitem">
            <span className="font-bold tabular-nums">{s.covered_count}/{s.total_requirements}</span>
            <span className="opacity-80">covered ({s.coverage_percentage}%)</span>
          </span>
          {stats.map((st) => (
            <span key={st.label} className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs ${st.classes}`} role="listitem">
              <span className="font-bold tabular-nums">{st.value}</span>
              <span className="opacity-80">{st.label}</span>
            </span>
          ))}
        </div>
        <p className="text-xs text-slate-400 mt-2">{report.honesty_note}</p>
      </div>

      {/* Partitioned two-column layout: critical left, everything else right.
          Columns grow independently (items-start); stack on narrow screens. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
        <div className="space-y-5 min-w-0">
          <GapGroup
            title="Critical gaps"
            description="Mandatory requirements that are missing or unverifiable. These gate the overall fit."
            items={report.critical_gaps}
            emptyHint="No mandatory requirements are missing."
            accent="red"
          />
        </div>
        <div className="space-y-5 min-w-0">
          <GapGroup
            title="Preferred gaps"
            description="Nice-to-have qualifications that would strengthen the application."
            items={report.preferred_gaps}
            emptyHint="All preferred requirements are covered."
            accent="amber"
          />
          <GapGroup
            title="Transferable skills"
            description="Related experience that partially applies. Related skills are never counted as direct experience."
            items={report.transferable_skills}
            emptyHint="No transferable-skill evidence to strengthen."
            accent="indigo"
          />
          <GapGroup
            title="Insufficient evidence"
            description="The resume does not provide enough verifiable evidence — distinct from an explicit miss."
            items={report.insufficient_evidence}
            emptyHint="Every requirement has verifiable evidence or is clearly missing."
            accent="slate"
          />
        </div>
      </div>

      <div className="ai-card px-4 py-3.5">
        <h3 className="text-sm font-bold text-white tracking-tight mb-2 tabular-nums">
          Already covered <span className="text-slate-500 font-semibold">({report.covered_requirements.length})</span>
        </h3>
        {report.covered_requirements.length === 0 ? (
          <p className="text-[13px] text-slate-500 italic">No requirements are fully covered yet.</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5" aria-label="Satisfied requirements">
            {report.covered_requirements.map((c) => (
              <li
                key={c.requirement_id}
                className="rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-0.5 text-xs font-medium text-emerald-300"
                title={c.requirement_text}
              >
                ✓ {c.normalized_requirement}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
