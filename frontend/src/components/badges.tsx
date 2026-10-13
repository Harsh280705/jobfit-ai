import type { ReactNode } from 'react';
import { STATUS_LABEL, type Match, type Requirement, type RequirementStatus } from '../types';

/** Status metadata for the dark bluish-black theme (presentation only — statuses/scores untouched). */
export const STATUS_META: Record<RequirementStatus, { label: string; short: string; icon: string; classes: string; dot: string }> = {
  FULLY_SATISFIED: { label: 'Fully Satisfied', short: 'Satisfied', icon: '✓', classes: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40', dot: 'bg-emerald-400' },
  PARTIALLY_SATISFIED: { label: 'Partially Satisfied', short: 'Partial', icon: '◐', classes: 'bg-amber-500/15 text-amber-300 border-amber-500/40', dot: 'bg-amber-400' },
  TRANSFERABLE: { label: 'Transferable', short: 'Transferable', icon: '↗', classes: 'bg-indigo-500/15 text-indigo-300 border-indigo-400/40', dot: 'bg-indigo-400' },
  MISSING: { label: 'Missing', short: 'Missing', icon: '×', classes: 'bg-red-500/15 text-red-300 border-red-500/40', dot: 'bg-red-400' },
  INSUFFICIENT_EVIDENCE: { label: 'Insufficient Evidence', short: 'No evidence', icon: '!', classes: 'bg-slate-500/15 text-slate-300 border-slate-500/40', dot: 'bg-slate-400' },
  CONTRADICTORY: { label: 'Contradictory', short: 'Conflict', icon: '⚠', classes: 'bg-rose-500/15 text-rose-300 border-rose-500/40', dot: 'bg-rose-400' },
};

export function StatusBadge({ status, compact = false }: { status: RequirementStatus; compact?: boolean }) {
  const fallback = STATUS_LABEL[status];
  const m = STATUS_META[status];
  if (!m) {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded-full border bg-slate-500/15 text-slate-200 border-slate-500/40">{fallback?.label ?? status}</span>;
  }
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded-full border whitespace-nowrap ${m.classes}`}
      aria-label={`Status: ${m.label}`}
    >
      <span className="text-xs leading-none" aria-hidden="true">{m.icon}</span>
      {compact ? m.short : m.label}
    </span>
  );
}

export function StatusDot({ status }: { status: RequirementStatus }) {
  const m = STATUS_META[status];
  return <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${m?.dot ?? 'bg-slate-400'}`} aria-hidden="true" />;
}

/** Slim horizontal progress bar. */
export function ScoreBar({ label, value, tone = 'indigo' }: { label: string; value: number; tone?: string }) {
  const tones: Record<string, string> = {
    indigo: 'bg-indigo-500',
    green: 'bg-emerald-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
    blue: 'bg-indigo-400',
  };
  return (
    <div className="mb-2 last:mb-0">
      <div className="flex justify-between items-baseline text-xs">
        <span className="text-slate-300">{label}</span>
        <span className="font-semibold text-white tabular-nums">{value}%</span>
      </div>
      <div className="h-1.5 bg-[#1c2a58] rounded-full overflow-hidden mt-1">
        <div className={`h-1.5 rounded-full ${tones[tone] ?? tones.indigo}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      </div>
    </div>
  );
}

/** Small SVG donut for the overall-fit hero. Value 0–100. */
export function Donut({ value, size = 76, stroke = 8, color }: { value: number; size?: number; stroke?: number; color?: string }) {
  const v = Math.min(100, Math.max(0, value ?? 0));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const auto = color ?? (v >= 75 ? '#34d399' : v >= 50 ? '#fbbf24' : v >= 25 ? '#fb923c' : '#f87171');
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0 -rotate-90" role="img" aria-label={`Overall fit ${v} percent`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="#1e2b54" strokeWidth={stroke} fill="none" />
      <circle
        cx={size / 2} cy={size / 2} r={r} stroke={auto} strokeWidth={stroke} fill="none"
        strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c - (v / 100) * c}
      />
    </svg>
  );
}

/** Dark filter chip with visible count. */
export function FilterChip({ active, count, onClick, children, tone = 'indigo' }: {
  active: boolean; count?: number; onClick: () => void; children: ReactNode; tone?: string;
}) {
  const activeTones: Record<string, string> = {
    indigo: 'bg-indigo-500 border-indigo-400 text-white',
    green: 'bg-emerald-600 border-emerald-500 text-white',
    amber: 'bg-amber-500 border-amber-400 text-slate-950',
    blue: 'bg-indigo-500 border-indigo-400 text-white',
    red: 'bg-red-600 border-red-500 text-white',
    orange: 'bg-orange-500 border-orange-400 text-slate-950',
    rose: 'bg-rose-600 border-rose-500 text-white',
    gray: 'bg-slate-200 border-slate-200 text-slate-900',
  };
  void tone;
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full border transition-colors focus-visible:outline-2 focus-visible:outline-indigo-400 ${
        active ? (activeTones[tone] ?? activeTones.indigo) : 'bg-[#101b3a] border-[#2a3a6e] text-slate-300 hover:border-indigo-400/60 hover:text-white'
      }`}
    >
      {children}
      {count !== undefined && (
        <span className={`min-w-[20px] text-center px-1 rounded-full text-[11px] font-semibold tabular-nums ${active ? 'bg-black/25 text-inherit' : 'bg-white/10 text-slate-300'}`}>
          {count}
        </span>
      )}
    </button>
  );
}

/** Compact summary chip used in the requirement-overview strip. */
export function StatChip({ label, value, tone }: { label: string; value: number | string; tone: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs ${tone}`}>
      <span className="font-bold tabular-nums">{value}</span>
      <span className="opacity-80">{label}</span>
    </span>
  );
}

/** Dark tones for the overview stat chips — restrained, readable on blue-black. */
export const OVERVIEW_TONES = {
  indigo: 'bg-indigo-500/15 text-indigo-200 border-indigo-400/30',
  gray: 'bg-white/5 text-slate-300 border-white/10',
  green: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  amber: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  blue: 'bg-indigo-500/15 text-indigo-200 border-indigo-400/30',
  red: 'bg-red-500/15 text-red-300 border-red-500/30',
  orange: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
  rose: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
};

/**
 * Compact replacement for the old full-page tree.
 * Kept under the same export name so existing imports keep working,
 * but now renders a dense overview strip instead of a tall list.
 */
export function RequirementTree({ requirements, matches }: { requirements: Requirement[]; matches?: Match[] }) {
  const core = requirements.filter((r) => r.mandatory);
  const pref = requirements.filter((r) => !r.mandatory);
  const byId = new Map((matches ?? []).map((m) => [m.requirement_id, m.status]));
  const count = (list: Requirement[], s: string) => list.filter((r) => byId.get(r.id) === s).length;
  const satisfied = count(requirements, 'FULLY_SATISFIED');
  const partial = count(requirements, 'PARTIALLY_SATISFIED');
  const transfer = count(requirements, 'TRANSFERABLE');
  const missing = count(requirements, 'MISSING');
  return (
    <div className="ai-card px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-white">Requirement Overview</h3>
        <span className="text-xs text-slate-400">{requirements.length} total</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <StatChip label="mandatory" value={core.length} tone={OVERVIEW_TONES.indigo} />
        <StatChip label="preferred" value={pref.length} tone={OVERVIEW_TONES.gray} />
        <StatChip label="satisfied" value={satisfied} tone={OVERVIEW_TONES.green} />
        <StatChip label="partial" value={partial} tone={OVERVIEW_TONES.amber} />
        <StatChip label="transferable" value={transfer} tone={OVERVIEW_TONES.blue} />
        <StatChip label="missing" value={missing} tone={OVERVIEW_TONES.red} />
      </div>
      {(core.length > 0 || pref.length > 0) && (
        <div className="mt-2.5 pt-2.5 border-t border-[#1e2b54] grid sm:grid-cols-2 gap-2 text-xs text-slate-400">
          <p className="truncate" title={core.map((r) => r.normalized_requirement).join('; ')}>
            <span className="font-semibold text-slate-200">Core · </span>
            {core.slice(0, 3).map((r) => r.normalized_requirement).join(' · ') || '—'}
            {core.length > 3 && ` +${core.length - 3} more`}
          </p>
          <p className="truncate" title={pref.map((r) => r.normalized_requirement).join('; ')}>
            <span className="font-semibold text-slate-200">Preferred · </span>
            {pref.slice(0, 3).map((r) => r.normalized_requirement).join(' · ') || '—'}
            {pref.length > 3 && ` +${pref.length - 3} more`}
          </p>
        </div>
      )}
    </div>
  );
}
