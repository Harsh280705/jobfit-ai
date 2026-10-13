import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { runEvaluation } from '../services/api';
import { EmptyState, ErrorCard, PageHeader, Skeleton } from '../components/ui';
import type { EvaluationMethodMetrics, EvaluationResponse } from '../types';

const METHODS = ['keyword', 'tfidf', 'semantic', 'proposed', 'rl'];

function methodLabel(k: string): string {
  if (k === 'tfidf') return 'TF-IDF baseline';
  if (k === 'proposed') return 'Proposed method';
  if (k === 'rl') return 'RL-enhanced';
  return `${k[0].toUpperCase()}${k.slice(1)} baseline`;
}

function MethodCard({ name, m, highlight }: { name: string; m: EvaluationMethodMetrics; highlight: boolean }) {
  const cells: [string, number][] = [
    ['Acc', m.accuracy],
    ['Prec', m.precision],
    ['Rec', m.recall],
  ];
  return (
    <div className={`rounded-2xl border p-3.5 transition-colors ${highlight ? 'border-indigo-500/40 bg-indigo-500/[0.07] shadow-[0_0_24px_rgba(99,102,241,0.25)]' : 'ai-card'}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[13px] font-semibold text-zinc-100">{methodLabel(name)}</p>
        {highlight && <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-200 bg-indigo-500/20 border border-indigo-500/30 rounded px-1.5 py-0.5">Ours</span>}
      </div>
      <p className="mt-1.5 text-[22px] font-bold text-white tabular-nums">F1 {m.f1}</p>
      <div className="mt-1 grid grid-cols-3 gap-1 text-center">
        {cells.map(([l, v]) => (
          <div key={l} className="rounded-md bg-black/30 border border-white/[0.06] py-1">
            <p className="text-[10px] uppercase tracking-wider text-zinc-600">{l}</p>
            <p className="text-[13px] font-semibold tabular-nums text-zinc-200">{v}</p>
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex gap-1.5 text-[11px] text-zinc-500">
        <span className="flex-1 rounded-md bg-black/30 border border-white/[0.06] py-1 text-center">FPR <strong className="tabular-nums text-zinc-200">{m.false_positive_rate}</strong></span>
        <span className="flex-1 rounded-md bg-black/30 border border-white/[0.06] py-1 text-center">FNR <strong className="tabular-nums text-zinc-200">{m.false_negative_rate}</strong></span>
      </div>
    </div>
  );
}

export default function Research() {
  const [results, setResults] = useState<EvaluationResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function run() {
    setBusy(true);
    setError('');
    try {
      setResults(await runEvaluation());
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || (e instanceof Error ? e.message : 'Evaluation failed'));
    } finally {
      setBusy(false);
    }
  }

  function exportJson() {
    if (!results) return;
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'evaluation.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const ordered = results
    ? METHODS.filter((m) => results.results[m]).concat(Object.keys(results.results).filter((k) => !METHODS.includes(k)))
    : [];
  const chartData = ordered.map((method) => {
    const m = (results as EvaluationResponse).results[method];
    return { method, F1: m.f1, Precision: m.precision, Recall: m.recall, FPR: m.false_positive_rate };
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Research & Evaluation"
        subtitle="Compare the proposed requirement-aware approach against baseline matching methods."
        actions={
          <>
            <button
              onClick={run}
              disabled={busy}
              className="ai-btn-primary px-4 py-1.5 text-[12.5px] disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
            >
              {busy ? 'Running…' : 'Run Evaluation'}
            </button>
            {results && (
              <button onClick={exportJson} className="ai-btn-ghost px-4 py-1.5 text-[12.5px]">
                Export JSON
              </button>
            )}
          </>
        }
      />

      {error && <ErrorCard message={error} onRetry={run} />}

      {busy && !results && (
        <div className="space-y-3" role="status" aria-label="Running evaluation">
          <Skeleton className="h-4 w-48" />
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
            {METHODS.map((k) => (
              <div key={k} className="ai-card p-3.5 space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-7 w-20" />
                <Skeleton className="h-8 w-full" />
              </div>
            ))}
          </div>
        </div>
      )}

      {!busy && !results && !error && (
        <EmptyState
          title="No evaluation results yet"
          hint="Run the evaluation to measure keyword, TF-IDF, and semantic baselines against the proposed method on the annotated dataset."
          action={
            <button onClick={run} className="ai-btn-primary px-4 py-1.5 text-[12.5px]">
              Run Evaluation
            </button>
          }
        />
      )}

      {results && (
        <div className="space-y-3">
          <p className="text-[12px] text-zinc-500 tabular-nums">Dataset: {results.dataset} · {results.n_cases} cases · measured values, nothing fabricated</p>
          {results.results.proposed && results.results.rl && (
            <div className="ai-card p-3.5 text-[12px] text-zinc-400 tabular-nums" aria-label="RL vs existing matcher">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">RL research comparison</p>
              <p className="mt-1">
                Existing matcher F1 <strong className="text-zinc-100">{results.results.proposed.f1}</strong>
                <span className="mx-2 text-zinc-700">·</span>
                RL matcher F1 <strong className="text-zinc-100">{results.results.rl.f1}</strong>
                <span className="mx-2 text-zinc-700">·</span>
                Existing matcher FPR <strong className="text-zinc-100">{results.results.proposed.false_positive_rate}</strong>
                <span className="mx-2 text-zinc-700">·</span>
                RL matcher FPR <strong className="text-zinc-100">{results.results.rl.false_positive_rate}</strong>
              </p>
              {results.ablation && (
                <p className="mt-0.5 text-zinc-500">
                  Decisions changed by RL: {results.ablation.n_changed} · correct changes: {results.ablation.n_changed_correct} · incorrect: {results.ablation.n_changed_incorrect} ·
                  false positives {results.ablation.base_false_positives}→{results.ablation.rl_false_positives} ·
                  false negatives {results.ablation.base_false_negatives}→{results.ablation.rl_false_negatives}
                </p>
              )}
            </div>
          )}
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
            {ordered.map((k) => (
              <MethodCard key={k} name={k} m={results.results[k]} highlight={k === 'proposed'} />
            ))}
          </div>

          <div className="ai-card p-3.5" style={{ height: 300 }}>
            <ResponsiveContainer>
              <BarChart data={chartData} barSize={22}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="method" tick={{ fontSize: 11, fill: '#71717a' }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} tickLine={false} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: '#71717a' }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0b0d15', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 12, color: '#f4f4f5' }}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: '#a1a1aa' }} />
                <Bar dataKey="F1" fill="#818cf8" radius={[3, 3, 0, 0]} />
                <Bar dataKey="Precision" fill="#34d399" radius={[3, 3, 0, 0]} />
                <Bar dataKey="Recall" fill="#fbbf24" radius={[3, 3, 0, 0]} />
                <Bar dataKey="FPR" fill="#f87171" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="ai-card overflow-hidden overflow-x-auto">
            <table className="w-full min-w-[560px] text-[13px]">
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-zinc-600 border-b border-white/[0.06]">
                  <th className="p-2.5 text-left font-semibold">Method</th>
                  <th className="p-2.5 font-semibold">Acc</th><th className="p-2.5 font-semibold">Prec</th>
                  <th className="p-2.5 font-semibold">Rec</th><th className="p-2.5 font-semibold">F1</th>
                  <th className="p-2.5 font-semibold">FPR</th><th className="p-2.5 font-semibold">FNR</th>
                </tr>
              </thead>
              <tbody>
                {ordered.map((k) => {
                  const m = results.results[k];
                  return (
                    <tr key={k} className={`border-t border-white/[0.04] text-center tabular-nums ${k === 'proposed' ? 'bg-indigo-500/[0.06] text-white font-semibold' : 'text-zinc-300'}`}>
                      <td className="p-2.5 text-left font-medium">{methodLabel(k)}</td>
                      <td className="p-2.5">{m.accuracy}</td><td className="p-2.5">{m.precision}</td>
                      <td className="p-2.5">{m.recall}</td><td className="p-2.5 font-bold">{m.f1}</td>
                      <td className="p-2.5">{m.false_positive_rate}</td><td className="p-2.5">{m.false_negative_rate}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.015] px-4 py-3 text-[12px] text-zinc-500 leading-5">
            <p className="font-semibold text-zinc-300">About these numbers</p>
            <p className="mt-0.5">
              Metrics are computed live by <span className="font-mono">POST /evaluation/run</span> over the
              annotated dataset ({results.n_cases} cases). F1 and false-positive rate are the primary comparison
              signals. Results reflect the seeded dataset — small or skewed samples limit generalizability.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
