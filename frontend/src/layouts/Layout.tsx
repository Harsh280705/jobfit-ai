import { useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';

// Research / Evaluation intentionally omitted from user-facing navigation.
// The /research route and backend evaluation API remain intact but undiscoverable.
const LINKS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/new', label: 'New Analysis', end: false },
];

function linkClass({ isActive }: { isActive: boolean }): string {
  return `px-3 py-1.5 rounded-lg text-sm transition-colors ${
    isActive
      ? 'bg-indigo-500/15 text-indigo-200 font-semibold border border-indigo-400/40'
      : 'text-slate-300 border border-transparent hover:bg-white/5 hover:text-white'
  }`;
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="ai-canvas min-h-screen text-slate-100 flex flex-col">
      <nav className="border-b border-[#1e2b54] bg-[#080f28]/95 backdrop-blur text-sm sticky top-0 z-10" aria-label="Main navigation">
        <div className="ai-shell px-4 sm:px-6 lg:px-8 py-2.5 flex gap-2 items-center">
          <Link to="/" className="font-bold text-lg tracking-tight mr-3 shrink-0 text-white" aria-label="JobFit AI home">
            JobFit <span className="text-indigo-400">AI</span>
          </Link>
          <div className="hidden sm:flex gap-1 items-center">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className={linkClass}>
                {l.label}
              </NavLink>
            ))}
          </div>
          <button
            className="sm:hidden ml-auto px-3 py-1.5 rounded-lg text-slate-200 border border-[#2a3a6e] bg-[#101b3a] hover:bg-[#16224a]"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label="Toggle navigation"
          >
            ☰ Menu
          </button>
        </div>
        {open && (
          <div className="sm:hidden px-4 pb-3 flex flex-col gap-1">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className={linkClass} onClick={() => setOpen(false)}>
                {l.label}
              </NavLink>
            ))}
          </div>
        )}
      </nav>
      <main className="flex-1 w-full">
        <div className="ai-shell px-4 sm:px-6 lg:px-8 py-6">
          <Outlet />
        </div>
      </main>
      <footer className="border-t border-[#1e2b54] bg-[#080f28]">
        <p className="ai-shell px-4 sm:px-6 lg:px-8 py-3 text-xs text-slate-400">
          JobFit AI — requirement-aware resume matching · Evidence-backed fit, gated on mandatory requirements
        </p>
      </footer>
    </div>
  );
}
