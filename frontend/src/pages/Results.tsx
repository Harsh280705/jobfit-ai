import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { fetchAnalysis } from '../services/api';
import { Donut, FilterChip, ScoreBar } from '../components/badges';
import { RequirementOverview } from '../components/RequirementOverview';
import { RequirementRow } from '../components/RequirementRow';
import { GapAnalysisSection } from '../components/GapAnalysis';
import { CardSkeletonGrid, EmptyState, ErrorCard, GhostLink, ListSkeleton, PrimaryLink, ProgressBar } from '../components/ui';
import { shortId } from '../utils/format';
import type { AnalysisDetail, Match, Requirement, RequirementStatus } from '../types';

type Filter = 'All' | RequirementStatus | 'Mandatory Only' | 'Preferred Only';

const FILTERS: { key: Filter; label: string; tone: string }[] = [
  { key: 'All', label: 'All', tone: 'indigo' },
  { key: 'FULLY_SATISFIED', label: '✓ Fully satisfied', tone: 'green' },
  { key: 'PARTIALLY_SATISFIED', label: '◐ Partially satisfied', tone: 'amber' },
  { key: 'TRANSFERABLE', label: '↗ Transferable', tone: 'blue' },
  { key: 'MISSING', label: '× Missing', tone: 'red' },
  { key: 'INSUFFICIENT_EVIDENCE', label: '! Insufficient evidence', tone: 'orange' },
  { key: 'CONTRADICTORY', label: '⚠ Contradictory', tone: 'rose' },
  { key: 'Mandatory Only', label: 'Mandatory only', tone: 'gray' },
  { key: 'Preferred Only', label: 'Preferred only', tone: 'gray' },
];

interface Row {
  req: Requirement;
  match: Match | undefined;
}

function passesFilter(row: Row, filter: Filter): boolean {
  if (filter === 'All') return true;
  if (filter === 'Mandatory Only') return row.req.mandatory;
  if (filter === 'Preferred Only') return !row.req.mandatory;
  return row.match?.status === filter;
}

function eligibilityClasses(eligibility: string | undefined, overall: number): string {
  const e = (eligibility ?? '').toUpperCase();
  if (e.includes('NOT ELIGIBLE') || e.includes('NOT QUALIFIED') || e.includes('FAIL')) return 'bg-red-500/15 text-red-300 border-red-500/40';
  if (e.includes('ELIGIBLE') || e.includes('QUALIFIED') || e.includes('STRONG') || overall >= 75) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40';
  if (overall >= 50) return 'bg-amber-500/15 text-amber-300 border-amber-500/40';
  return 'bg-red-500/15 text-red-300 border-red-500/40';
}

function analysisStatusPill(status: string): string {
  const s = status.toUpperCase();
  if (s === 'COMPLETED') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40';
  if (s === 'FAILED') return 'bg-red-500/15 text-red-300 border-red-500/40';
  return 'bg-amber-500/15 text-amber-300 border-amber-500/40';
}

export default function Results() {
  const { id } = useParams();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['analysis', id],
    queryFn: () => fetchAnalysis(id ?? ''),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.status === 'COMPLETED' || q.state.data?.status === 'FAILED' ? false : 1500),
  });
  const [filter, setFilter] = useState<Filter>('All');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const detail: AnalysisDetail | undefined = data;

  const rows: Row[] = useMemo(() => {
    if (!detail) return [];
    const byReq = new Map(detail.matches.map((m) => [m.requirement_id, m]));
    return detail.requirements
      .map((req) => ({ req, match: byReq.get(req.id) }))
      .filter((row) => passesFilter(row, filter));
  }, [detail, filter]);

  const counts = useMemo(() => {
    const c: Record<Filter, number> = {
      All: 0, FULLY_SATISFIED: 0, PARTIALLY_SATISFIED: 0, TRANSFERABLE: 0,
      MISSING: 0, INSUFFICIENT_EVIDENCE: 0, CONTRADICTORY: 0,
      'Mandatory Only': 0, 'Preferred Only': 0,
    };
    if (!detail) return c;
    const byReq = new Map(detail.matches.map((m) => [m.requirement_id, m.status]));
    for (const r of detail.requirements) {
      c.All += 1;
      c[r.mandatory ? 'Mandatory Only' : 'Preferred Only'] += 1;
      const st = byReq.get(r.id);
      if (st) c[st] += 1;
    }
    return c;
  }, [detail]);

  const satisfied = counts.FULLY_SATISFIED;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <p className="text-sm text-slate-400" role="status">Loading analysis…</p>
        <CardSkeletonGrid count={4} />
        <ListSkeleton rows={4} />
      </div>
    );
  }
  if (error || !detail) {
    return (
      <div className="space-y-6">
        <ErrorCard message="Failed to load analysis. The backend may be unavailable." onRetry={() => refetch()} />
      </div>
    );
  }
  if (detail.status === 'QUEUED' || detail.status === 'PROCESSING') {
    return (
      <div className="max-w-xl space-y-3">
        <h1 className="text-2xl font-bold text-white tracking-tight">Analysis {detail.status}… ({detail.progress}%)</h1>
        <ProgressBar value={detail.progress} />
        <button className="text-sm font-medium underline text-indigo-300 hover:text-indigo-200" onClick={() => refetch()}>Refresh</button>
      </div>
    );
  }
  if (detail.status === 'FAILED') {
    return (
      <div className="max-w-xl space-y-3">
        <h1 className="text-2xl font-bold text-white tracking-tight">Requirement analysis failed.</h1>
        <ErrorCard message={detail.error || 'Analysis failed for an unknown reason.'} />
        <p className="text-sm text-slate-400">Retry from New Analysis.</p>
      </div>
    );
  }

  const s = detail.score;
  const overall = s?.overall ?? 0;
  const toggle = (rid: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(rid)) next.delete(rid);
      else next.add(rid);
      return next;
    });

  return (
    <div className="w-full space-y-6">
      {/* A. Compact horizontal analysis header */}
      <header className="ai-card px-4 sm:px-5 py-4 flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl sm:text-2xl leading-7 font-bold text-white tracking-tight">Job fit analysis</h1>
            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-semibold rounded-full border ${analysisStatusPill(detail.status)}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current" aria-hidden="true" />{detail.status}
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Analysis <span className="font-mono text-slate-200">#{shortId(detail.id)}</span>
            <span className="mx-1.5 text-slate-600">·</span>{detail.requirements.length} requirements
            <span className="mx-1.5 text-slate-600">·</span>{detail.matches.length} evaluated
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <GhostLink to="/">← Back</GhostLink>
          <PrimaryLink to="/new">+ New Analysis</PrimaryLink>
        </div>
      </header>

      {/* B. Fit summary — values rendered exactly as returned by the backend */}
      <section aria-label="Fit summary" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="ai-card ai-glow p-4 flex items-center gap-3">
          <div className="relative shrink-0">
            <Donut value={overall} />
            <span className="absolute inset-0 flex items-center justify-center text-[15px] font-bold text-white tabular-nums">{overall}%</span>
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">Overall fit</p>
            <p className="text-2xl leading-7 font-bold text-white tabular-nums">{overall}%</p>
            <span className={`inline-block mt-1 px-1.5 py-0.5 text-[11px] font-semibold rounded border leading-4 ${eligibilityClasses(s?.eligibility, overall)}`}>
              {s?.eligibility || '—'}
            </span>
          </div>
        </div>

        <div className="ai-card p-4 flex flex-col min-h-[132px]">
          <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">Mandatory coverage</p>
          <p className="text-2xl leading-8 font-bold text-white tabular-nums mt-1">{s?.mandatory_coverage ?? 0}%</p>
          <p className="text-xs text-slate-400 tabular-nums">{s?.mandatory_satisfied ?? 0} / {s?.mandatory_total ?? 0} satisfied</p>
          <div className="h-1.5 bg-[#1c2a58] rounded-full overflow-hidden mt-auto pt-0 translate-y-1">
            <div className="h-1.5 bg-indigo-500 rounded-full" style={{ width: `${Math.min(100, s?.mandatory_coverage ?? 0)}%` }} />
          </div>
        </div>

        <div className="ai-card p-4 flex flex-col min-h-[132px]">
          <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">Experience fit</p>
          <p className="text-2xl leading-8 font-bold text-white tabular-nums mt-1">{s?.experience_fit ?? 0}%</p>
          <p className="text-xs text-slate-400">
            {(s?.experience_fit ?? 0) === 0 ? 'No matching years of experience found' : `Preferred coverage ${s?.preferred_coverage ?? 0}% · Skill fit ${s?.skill_fit ?? 0}%`}
          </p>
        </div>

        <div className="ai-card p-4 flex flex-col min-h-[132px]">
          <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">Evidence confidence</p>
          <p className="text-2xl leading-8 font-bold text-white tabular-nums mt-1">{s?.evidence_confidence ?? 0}%</p>
          <div className="mt-2">
            <ScoreBar label="Preferred coverage" value={s?.preferred_coverage ?? 0} tone="green" />
          </div>
        </div>
      </section>

      <RequirementOverview requirements={detail.requirements} matches={detail.matches} />

      <section aria-label="Requirement analysis" className="ai-card px-4 sm:px-5 py-4">
        <div className="ai-rule mb-3">
          <h2 className="text-lg font-bold text-white tracking-tight">Requirement analysis</h2>
          <p className="text-xs text-slate-400 tabular-nums ml-auto">
            {detail.requirements.length} requirements · {satisfied} fully satisfied
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5 mb-4" role="group" aria-label="Filter requirements">
          {FILTERS.map((f) => (
            <FilterChip key={f.key} active={filter === f.key} count={counts[f.key]} tone={f.tone} onClick={() => setFilter(f.key)}>
              {f.label}
            </FilterChip>
          ))}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
          {rows.map(({ req, match }) => (
            <RequirementRow
              key={req.id}
              analysisId={detail.id}
              req={req}
              match={match}
              expanded={expanded.has(req.id)}
              onToggle={() => toggle(req.id)}
            />
          ))}
          {rows.length === 0 && (
            <div className="xl:col-span-2">
              <EmptyState
                title={`No requirements match “${filter}”`}
                hint="Try a different filter to see more requirements."
                action={<button onClick={() => setFilter('All')} className="text-sm font-semibold text-indigo-300 hover:underline">Show all requirements</button>}
              />
            </div>
          )}
        </div>
      </section>

      <GapAnalysisSection analysisId={detail.id} />
    </div>
  );
}
