import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchAnalyses } from '../services/api';
import { CardSkeletonGrid, EmptyState, ErrorCard, PageHeader, PrimaryLink, StatCard } from '../components/ui';
import { shortId } from '../utils/format';
import type { AnalysisSummary } from '../types';

function statusPill(status: string): string {
  const s = (status ?? '').toUpperCase();
  if (s === 'COMPLETED') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40';
  if (s === 'FAILED') return 'bg-red-500/15 text-red-300 border-red-500/40';
  return 'bg-amber-500/15 text-amber-300 border-amber-500/40';
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export default function Dashboard() {
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ['analyses'], queryFn: fetchAnalyses });

  if (isLoading) {
    return (
      <div className="w-full space-y-6">
        <PageHeader
          title="Dashboard"
          subtitle="Track every resume–job analysis. Scores are computed by the backend and shown exactly as returned."
        />
        <CardSkeletonGrid count={4} />
      </div>
    );
  }
  if (error) {
    return (
      <div className="w-full space-y-6">
        <PageHeader
          title="Dashboard"
          subtitle="Track every resume–job analysis. Scores are computed by the backend and shown exactly as returned."
        />
        <ErrorCard
          message="Backend unavailable. Start it with `make backend` or `docker compose up`, then try again."
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const rows: AnalysisSummary[] = data ?? [];
  const scored = rows.filter((r) => r.overall !== null && r.overall !== undefined);
  const avg = scored.length ? (scored.reduce((s, r) => s + (r.overall ?? 0), 0) / scored.length).toFixed(1) : null;
  const strong = scored.filter((r) => (r.overall ?? 0) >= 75).length;
  const completed = rows.filter((r) => r.status === 'COMPLETED').length;
  const recent = rows.slice(0, 10);

  return (
    <div className="w-full space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle="Track every resume–job analysis. Overall fit is gated on mandatory requirements — select a row for the evidence behind each score."
        actions={<PrimaryLink to="/new">+ New Analysis</PrimaryLink>}
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" aria-label="Analysis summary">
        <StatCard label="Total analyses" value={rows.length} />
        <StatCard
          label="Average fit"
          value={avg !== null ? `${avg}%` : '—'}
          footer={<span>across {scored.length} scored {scored.length === 1 ? 'analysis' : 'analyses'}</span>}
        />
        <StatCard label="Strong fits (≥75%)" value={strong} />
        <StatCard label="Completed" value={completed} />
      </div>

      <section aria-label="Recent analyses" className="ai-card overflow-hidden">
        <div className="flex items-center justify-between px-4 sm:px-5 py-3 border-b border-[#1e2b54]">
          <h2 className="text-base font-semibold text-white">Recent analyses</h2>
          <span className="text-xs text-slate-400 tabular-nums">{rows.length} total</span>
        </div>
        {recent.length === 0 ? (
          <div className="p-4 sm:p-5">
            <EmptyState
              title="No analyses yet"
              hint="Upload a resume and a job description to get an evidence-backed fit report with requirement-level verdicts."
              action={<PrimaryLink to="/new">+ New Analysis</PrimaryLink>}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-slate-400 border-b border-[#1e2b54] bg-[#0a1230]">
                  <th scope="col" className="px-4 sm:px-5 py-2.5 font-semibold">Analysis</th>
                  <th scope="col" className="px-4 sm:px-5 py-2.5 font-semibold">Status</th>
                  <th scope="col" className="px-4 sm:px-5 py-2.5 font-semibold">Fit</th>
                  <th scope="col" className="px-4 sm:px-5 py-2.5 font-semibold">Created</th>
                  <th scope="col" className="px-4 sm:px-5 py-2.5 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((r) => (
                  <tr key={r.id} className="border-t border-[#16224a] hover:bg-white/5 transition-colors">
                    <td className="px-4 sm:px-5 py-3 font-mono text-xs text-slate-200">#{shortId(r.id)}</td>
                    <td className="px-4 sm:px-5 py-3">
                      <span className={`inline-block px-2 py-0.5 text-xs font-semibold rounded-full border ${statusPill(r.status)}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 sm:px-5 py-3 tabular-nums font-semibold text-white">
                      {r.overall !== null && r.overall !== undefined ? `${r.overall}%` : '—'}
                    </td>
                    <td className="px-4 sm:px-5 py-3 text-slate-400 text-xs whitespace-nowrap">{formatDate(r.created_at)}</td>
                    <td className="px-4 sm:px-5 py-3 text-right">
                      <Link
                        to={`/results/${r.id}`}
                        className="text-sm font-semibold text-indigo-300 hover:text-indigo-200 hover:underline rounded focus-visible:outline-2 focus-visible:outline-indigo-400"
                      >
                        View report →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
