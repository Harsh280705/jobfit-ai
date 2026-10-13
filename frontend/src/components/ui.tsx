import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

/** Compact page header: title, short description, right-aligned actions. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start gap-3">
      <div className="flex-1 min-w-0">
        <h1 className="text-xl sm:text-2xl leading-7 font-bold text-white tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-slate-300 mt-1 max-w-3xl leading-6">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
}

export function PrimaryLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="ai-btn-primary px-4 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
    >
      {children}
    </Link>
  );
}

export function GhostLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="ai-btn-ghost px-4 py-2 text-sm">
      {children}
    </Link>
  );
}

/** Metric card: label + value + optional footer. Consistent height via flex. */
export function StatCard({
  label,
  value,
  footer,
}: {
  label: string;
  value: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="ai-card p-4 flex flex-col min-h-[104px]">
      <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">{label}</p>
      <p className="text-2xl leading-8 font-bold text-white tabular-nums mt-1">{value}</p>
      {footer && <div className="mt-1 text-xs text-slate-400">{footer}</div>}
    </div>
  );
}

/** Plain card container used across pages. */
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`ai-card ${className}`}>{children}</div>;
}

/** Dark skeleton block for loading states. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-[#1c2a58] rounded ${className}`} aria-hidden="true" />;
}

export function CardSkeletonGrid({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4" role="status" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="ai-card p-4 space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-16" />
          <Skeleton className="h-2 w-full" />
        </div>
      ))}
    </div>
  );
}

export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="ai-card px-4 py-3 space-y-2">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-2/3" />
          <Skeleton className="h-3 w-1/4" />
        </div>
      ))}
    </div>
  );
}

/** Dark error card — shows message, never stack traces. */
export function ErrorCard({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="ai-card p-5 text-center max-w-lg mx-auto" style={{ borderColor: '#7f1d1d', backgroundColor: '#1a1030' }}>
      <p className="text-sm font-semibold text-white">Something went wrong</p>
      <p className="text-sm text-slate-300 mt-1">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="ai-btn-ghost mt-3 px-4 py-2 text-sm">
          Try again
        </button>
      )}
    </div>
  );
}

/** Empty state with a next-step action. */
export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-[#2a3a6e] bg-[#0a1230] p-8 text-center">
      <p className="text-sm font-semibold text-white">{title}</p>
      <p className="text-sm text-slate-400 mt-1 max-w-md mx-auto">{hint}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

/** Thin progress bar (processing states). */
export function ProgressBar({ value }: { value: number }) {
  return (
    <div
      className="h-2 bg-[#1c2a58] rounded-full overflow-hidden"
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-2 bg-indigo-500 rounded-full transition-all"
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}
