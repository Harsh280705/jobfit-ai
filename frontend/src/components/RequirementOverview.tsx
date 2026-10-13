import { useState } from 'react';
import { OVERVIEW_TONES, StatChip } from './badges';
import type { Match, Requirement } from '../types';

const PREVIEW = 6;

function Group({ title, items, tone }: { title: string; items: Requirement[]; tone: string }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? items : items.slice(0, PREVIEW);
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-1.5">{title}</p>
      <div className="flex flex-wrap gap-1.5">
        {visible.map((r) => (
          <span
            key={r.id}
            title={r.raw_text}
            className={`inline-block max-w-[220px] truncate px-2 py-1 text-xs font-medium rounded-md border ${tone}`}
          >
            {r.normalized_requirement}
          </span>
        ))}
        {items.length > PREVIEW && (
          <button
            onClick={() => setShowAll((v) => !v)}
            className="px-2 py-1 text-xs font-medium rounded-md border border-dashed border-[#2a3a6e] text-slate-400 hover:text-white hover:border-indigo-400/60"
          >
            {showAll ? 'Show less' : `+${items.length - PREVIEW} more`}
          </button>
        )}
      </div>
    </div>
  );
}

/** Compact "Requirement Summary": status distribution + core/preferred groups. */
export function RequirementOverview({
  requirements,
  matches,
}: {
  requirements: Requirement[];
  matches: Match[];
}) {
  const core = requirements.filter((r) => r.mandatory);
  const pref = requirements.filter((r) => !r.mandatory);
  const byId = new Map(matches.map((m) => [m.requirement_id, m.status]));
  const n = (s: string) => requirements.filter((r) => byId.get(r.id) === s).length;
  return (
    <section aria-label="Requirement summary" className="ai-card px-4 sm:px-5 py-4 space-y-3">
      <div className="ai-rule">
        <h3 className="text-sm font-semibold text-white">Requirement summary</h3>
        <span className="text-xs text-slate-400 tabular-nums ml-auto">{requirements.length} total</span>
      </div>
      <div className="flex flex-wrap gap-1.5" role="list" aria-label="Requirement status counts">
        <StatChip label="mandatory" value={core.length} tone={OVERVIEW_TONES.indigo} />
        <StatChip label="preferred" value={pref.length} tone={OVERVIEW_TONES.gray} />
        <StatChip label="fully satisfied" value={n('FULLY_SATISFIED')} tone={OVERVIEW_TONES.green} />
        <StatChip label="partial" value={n('PARTIALLY_SATISFIED')} tone={OVERVIEW_TONES.amber} />
        <StatChip label="transferable" value={n('TRANSFERABLE')} tone={OVERVIEW_TONES.blue} />
        <StatChip label="missing" value={n('MISSING')} tone={OVERVIEW_TONES.red} />
        <StatChip label="insufficient evidence" value={n('INSUFFICIENT_EVIDENCE')} tone={OVERVIEW_TONES.orange} />
        <StatChip label="contradictory" value={n('CONTRADICTORY')} tone={OVERVIEW_TONES.rose} />
      </div>
      <div className="pt-3 border-t border-[#1e2b54] space-y-2.5">
        <Group title={`Mandatory · ${core.length}`} items={core} tone="bg-indigo-500/15 text-indigo-200 border-indigo-400/30" />
        <Group title={`Preferred · ${pref.length}`} items={pref} tone="bg-white/5 text-slate-300 border-white/10" />
      </div>
    </section>
  );
}
