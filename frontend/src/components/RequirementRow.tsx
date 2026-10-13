import { Link } from 'react-router-dom';
import { StatusBadge } from './badges';
import { shortId } from '../utils/format';
import type { Evidence, Match, Requirement } from '../types';

function truncate(text: string, n: number): string {
  return text.length > n ? `${text.slice(0, n)}…` : text;
}

/** Collapsible evidence block. Renders backend evidence verbatim; never invents content. */
export function EvidencePanel({ match, requiredYears }: { match: Match; requiredYears: number | null }) {
  const ev: Evidence[] = match.evidence ?? [];
  return (
    <div className="space-y-2">
      {ev.map((e, i) => (
        <blockquote
          key={i}
          className="border-l-2 border-indigo-400/60 bg-[#0a1230] rounded-r-lg px-3 py-2 text-[13px] text-slate-200 leading-5"
        >
          “{truncate(e.text, 600)}”
          <span className="block text-xs text-slate-400 mt-1">
            {[e.section, e.source].filter(Boolean).join(' · ')}
            {e.confidence !== undefined && e.confidence !== null ? ` · confidence ${e.confidence}` : ''}
            {e.relation ? ` · ${e.relation}` : ''}
          </span>
        </blockquote>
      ))}
      {match.explanation && (
        <p className="text-[13px] text-slate-300 leading-5">
          <span className="font-semibold text-white">Explanation: </span>
          {match.explanation}
        </p>
      )}
      {match.estimated_years !== undefined && match.estimated_years !== null && (
        <p className="text-xs text-slate-400">
          Estimated experience: {match.estimated_years} yrs{requiredYears ? ` (required ${requiredYears}+ yrs)` : ''}
        </p>
      )}
    </div>
  );
}

/** Compact requirement row with evidence-on-demand. */
export function RequirementRow({
  analysisId,
  req,
  match,
  expanded,
  onToggle,
}: {
  analysisId: string;
  req: Requirement;
  match: Match | undefined;
  expanded: boolean;
  onToggle: () => void;
}) {
  const ev = match?.evidence ?? [];
  const preview = ev[0]?.text ?? '';
  return (
    <article className="ai-card px-4 py-3 hover:border-indigo-400/40 transition-colors">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <div className="flex-1 min-w-[200px]">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Link
              to={`/requirements/${analysisId}/${req.id}`}
              title={`Open requirement ${shortId(req.id)}`}
              className="text-[15px] font-semibold text-white hover:text-indigo-300 hover:underline rounded"
            >
              {req.normalized_requirement}
            </Link>
            <span
              className={`inline-flex items-center px-1.5 py-px text-[10.5px] font-bold uppercase tracking-wide rounded border ${
                req.mandatory
                  ? 'bg-indigo-500/15 text-indigo-200 border-indigo-400/40'
                  : 'bg-white/5 text-slate-300 border-white/10'
              }`}
            >
              {req.mandatory ? 'Mandatory' : 'Preferred'}
            </span>
          </div>
          <p className="text-[13px] text-slate-300 leading-5 mt-0.5 line-clamp-2" title={req.raw_text}>
            {req.raw_text}
          </p>
          <p className="text-xs text-slate-400 mt-1">
            {req.category}
            {req.minimum_years ? ` · Requires ${req.minimum_years}+ yrs` : ''}
          </p>
        </div>
        <div className="flex items-center pt-0.5">
          {match ? <StatusBadge status={match.status} /> : <span className="text-xs text-slate-400">Not evaluated</span>}
        </div>
        <div className="text-right shrink-0 w-[92px]">
          <p className="text-[10.5px] font-semibold tracking-wider text-slate-400 uppercase">Confidence</p>
          <p className="text-[15px] font-bold text-white tabular-nums">
            {match?.confidence ?? '—'}
            {match?.confidence !== undefined && match?.confidence !== null ? '%' : ''}
          </p>
          {match && (
            <div className="h-1.5 bg-[#1c2a58] rounded-full overflow-hidden mt-1">
              <div className="h-1.5 bg-indigo-500 rounded-full" style={{ width: `${Math.min(100, match.confidence ?? 0)}%` }} />
            </div>
          )}
        </div>
      </div>

      {match?.rl_used && (
        <p className="mt-1.5 text-xs text-slate-400" title="Reinforcement-learning decision layer (additive; constraints stay authoritative)">
          RL decision: <span className="font-semibold text-slate-200">{match.rl_status ?? '—'}</span>
          {match.rl_confidence !== undefined && match.rl_confidence !== null && (
            <span className="tabular-nums"> · confidence {match.rl_confidence}</span>
          )}
          {match.rl_changed_decision ? (
            <span className="ml-1.5 rounded border border-amber-500/40 bg-amber-500/15 px-1 py-px text-[11px] font-semibold text-amber-300">
              changed by RL (base: {match.existing_status})
            </span>
          ) : (
            <span className="ml-1.5 text-slate-500">· agrees with base</span>
          )}
        </p>
      )}

      <div className="mt-2 pt-2 border-t border-[#1e2b54]">
        {ev.length === 0 ? (
          <p className="text-[13px] text-slate-500 italic">No supporting evidence found</p>
        ) : !expanded ? (
          <div className="flex items-center gap-2 min-w-0">
            <p className="flex-1 min-w-0 truncate text-[13px] text-slate-300">
              <span className="font-semibold text-slate-200 mr-1">Evidence:</span>“{truncate(preview, 140)}”
            </p>
            <button
              onClick={onToggle}
              aria-expanded={false}
              className="shrink-0 text-xs font-semibold text-indigo-300 hover:text-indigo-200 hover:underline rounded px-1 py-0.5"
            >
              Show evidence ({ev.length}) ▾
            </button>
          </div>
        ) : (
          <div>
            <button
              onClick={onToggle}
              aria-expanded={true}
              className="text-xs font-semibold text-indigo-300 hover:text-indigo-200 hover:underline rounded px-1 py-0.5 mb-2"
            >
              Hide evidence ▴
            </button>
            {match && <EvidencePanel match={match} requiredYears={req.minimum_years} />}
          </div>
        )}
      </div>
    </article>
  );
}
