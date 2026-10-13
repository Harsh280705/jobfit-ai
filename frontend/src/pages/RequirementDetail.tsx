import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { fetchRequirementDetail } from '../services/api';
import { StatusBadge } from '../components/badges';
import { ErrorCard, GhostLink, Skeleton } from '../components/ui';
import type { RequirementDetailResponse } from '../types';

export default function RequirementDetail() {
  const { analysisId, reqId } = useParams();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['req', analysisId, reqId],
    queryFn: () => fetchRequirementDetail(analysisId ?? '', reqId ?? ''),
    enabled: !!analysisId && !!reqId,
  });

  if (isLoading) {
    return (
      <div className="w-full max-w-5xl space-y-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-7 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <div className="ai-card p-4 space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="w-full max-w-5xl space-y-3">
        <GhostLink to={`/results/${analysisId}`}>← Back to analysis</GhostLink>
        <ErrorCard message="Failed to load this requirement." onRetry={() => refetch()} />
      </div>
    );
  }

  const detail: RequirementDetailResponse = data;
  const req = detail.requirement;
  const m = detail.match;

  return (
    <div className="w-full max-w-5xl space-y-4">
      <GhostLink to={`/results/${analysisId}`}>← Back to analysis</GhostLink>
      <div>
        <h1 className="text-xl font-bold text-white leading-6 tracking-tight">{req.raw_text}</h1>
        <p className="text-sm text-slate-400 mt-1">
          <span className={`inline-flex items-center px-1.5 py-px text-[11px] font-bold uppercase tracking-wide rounded border mr-1.5 ${req.mandatory ? 'bg-indigo-500/15 text-indigo-200 border-indigo-400/40' : 'bg-white/5 text-slate-300 border-white/10'}`}>
            {req.mandatory ? 'Mandatory' : 'Preferred'}
          </span>
          {req.category}
          {req.minimum_years ? ` · Requires ${req.minimum_years}+ yrs` : ''}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {m && <StatusBadge status={m.status} />}
          {m && <span className="text-sm text-slate-300 tabular-nums">Confidence {m.confidence}%</span>}
          {m?.rl_used && (
            <span className="text-xs text-slate-400 tabular-nums" title="Reinforcement-learning decision layer">
              RL: {m.rl_status ?? '—'}{m.rl_confidence != null ? ` (${m.rl_confidence})` : ''}
              {m.rl_changed_decision ? ` · changed base ${m.existing_status}` : ' · agrees with base'}
            </span>
          )}
        </div>
      </div>

      <div className="ai-card p-4 sm:p-5 text-sm space-y-4">
        <div className="grid sm:grid-cols-2 gap-3">
          <div className="rounded-xl bg-[#0a1230] border border-[#1e2b54] p-3">
            <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">Normalized requirement</p>
            <p className="mt-0.5 font-medium text-white">{req.normalized_requirement}</p>
          </div>
          <div className="rounded-xl bg-[#0a1230] border border-[#1e2b54] p-3">
            <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">Experience</p>
            <p className="mt-0.5 text-slate-300 tabular-nums">
              Required: {req.minimum_years ? `${req.minimum_years}+ yrs` : '—'}
              <span className="mx-1.5 text-slate-600">|</span>
              Estimated: {m?.estimated_years ?? 'n/a'}
            </p>
          </div>
        </div>

        <div>
          <h2 className="text-sm font-semibold text-white mb-2">Evidence</h2>
          {(m?.evidence ?? []).map((e, i) => (
            <blockquote key={i} className="border-l-2 border-indigo-400/60 bg-[#0a1230] rounded-r-lg pl-3 pr-2 py-2 my-2 text-[13px] text-slate-200 leading-5">
              “{e.text}”
              <span className="block text-xs text-slate-400 mt-1">
                {[e.section, e.source].filter(Boolean).join(' · ')}
                {e.confidence !== undefined && e.confidence !== null ? ` · confidence ${e.confidence}` : ''}
                {e.relation ? ` · ${e.relation}` : ''}
              </span>
            </blockquote>
          ))}
          {!m?.evidence?.length && <p className="text-sm text-slate-500 italic">No supporting evidence found.</p>}
        </div>

        {m?.explanation && (
          <div>
            <h2 className="text-sm font-semibold text-white mb-1">Matching explanation</h2>
            <p className="text-[13px] text-slate-300 leading-6">{m.explanation}</p>
          </div>
        )}
      </div>
    </div>
  );
}
