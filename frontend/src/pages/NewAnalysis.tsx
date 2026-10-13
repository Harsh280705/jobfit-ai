import { useRef, useState } from 'react';
import type { ChangeEvent, DragEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { createAnalysis, createJobText, createResumeText, fetchDocumentText, uploadDocument } from '../services/api';
import { PageHeader } from '../components/ui';

type Side = 'resume' | 'job_description';

function UploadZone({
  label,
  accept,
  fileName,
  loading,
  onFile,
  onClear,
  hint,
}: {
  label: string;
  accept: string;
  fileName: string;
  loading: boolean;
  onFile: (f: File) => void;
  onClear: () => void;
  hint: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const drop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };
  const pick = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) onFile(f);
    e.target.value = '';
  };
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={drop}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inputRef.current?.click(); } }}
      className={`cursor-pointer rounded-xl border-2 border-dashed px-4 py-4 text-center transition-colors focus-within:outline-2 focus-within:outline-indigo-400 ${
        drag
          ? 'border-indigo-400 bg-indigo-500/15'
          : 'border-[#2a3a6e] bg-[#0a1230] hover:border-indigo-400/70 hover:bg-indigo-500/10'
      }`}
      role="button"
      tabIndex={0}
      aria-label={label}
    >
      <input ref={inputRef} type="file" accept={accept} className="sr-only" onChange={pick} tabIndex={-1} />
      {loading ? (
        <p className="text-sm text-slate-300" role="status">Extracting text…</p>
      ) : fileName ? (
        <p className="text-sm text-slate-200">
          <span className="font-semibold text-emerald-300">✓ {fileName}</span>{' '}
          <button
            onClick={(e) => { e.stopPropagation(); onClear(); }}
            className="text-indigo-300 hover:text-indigo-200 hover:underline font-semibold rounded focus-visible:outline-2 focus-visible:outline-indigo-400"
          >
            Clear
          </button>
        </p>
      ) : (
        <div>
          <p className="text-sm text-slate-200">
            <span className="font-semibold text-indigo-300">Upload a file</span> or drag &amp; drop
          </p>
          <p className="text-xs text-slate-400 mt-1">{hint}</p>
        </div>
      )}
    </div>
  );
}

export default function NewAnalysis() {
  const [resumeText, setResumeText] = useState('');
  const [jobText, setJobText] = useState('');
  const [jobTitle, setJobTitle] = useState('ML Engineer');
  const [resumeFile, setResumeFile] = useState('');
  const [jobFile, setJobFile] = useState('');
  const [parsing, setParsing] = useState<Side | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const nav = useNavigate();

  async function fileToText(file: File, side: Side) {
    const setter = side === 'resume' ? setResumeText : setJobText;
    const nameSetter = side === 'resume' ? setResumeFile : setJobFile;
    setParsing(side);
    setError('');
    try {
      if (file.name.toLowerCase().endsWith('.txt')) {
        setter(await file.text());
      } else {
        const doc = await uploadDocument(file, side);
        setter(await fetchDocumentText(doc.id));
      }
      nameSetter(file.name);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not read that file.';
      setError(msg || 'Could not read that file.');
    } finally {
      setParsing(null);
    }
  }

  async function submit() {
    if (busy || parsing !== null) return;
    setBusy(true);
    setError('');
    try {
      if (!resumeText.trim() || !jobText.trim()) throw new Error('Both resume and job description are required.');
      if (!jobTitle.trim()) throw new Error('Job title is required.');
      const resume = await createResumeText(resumeText);
      const job = await createJobText(jobTitle, jobText);
      const analysis = await createAnalysis(resume.id, job.id);
      nav(`/results/${analysis.analysis_id}`);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || (e instanceof Error ? e.message : 'Analysis failed'));
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = resumeText.trim().length > 0 && jobText.trim().length > 0 && !busy && parsing === null;

  return (
    <div className="w-full space-y-6">
      <PageHeader
        title="New job fit analysis"
        subtitle="Paste text or upload files for both sides. Requirements are extracted automatically — the overall score is gated on mandatory requirements."
      />
      {error && (
        <p role="alert" className="text-sm text-red-300 bg-red-500/10 border border-red-500/40 rounded-xl px-4 py-3">
          {error}
        </p>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        <section aria-labelledby="resume-heading" className="ai-card p-5 space-y-3">
          <div className="flex items-baseline justify-between gap-2">
            <div>
              <h2 id="resume-heading" className="text-sm font-semibold text-white">1 · Resume</h2>
              <p className="text-xs text-slate-400 mt-0.5">Candidate experience, skills, and education.</p>
            </div>
            <span className="text-xs text-slate-400 tabular-nums shrink-0">{resumeText.length} chars</span>
          </div>
          <UploadZone
            label="Upload resume file"
            accept=".pdf,.docx,.txt"
            fileName={resumeFile}
            loading={parsing === 'resume'}
            hint="PDF, DOCX, or TXT — parsed by the backend text extractor"
            onFile={(f) => fileToText(f, 'resume')}
            onClear={() => { setResumeFile(''); setResumeText(''); }}
          />
          <label className="block">
            <span className="sr-only">Resume text</span>
            <textarea
              className="ai-input h-64 p-3 leading-6"
              placeholder="Paste resume text, or upload a file above…"
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
            />
          </label>
          <p className="text-xs text-slate-400">Only qualification-relevant content is scored.</p>
        </section>

        <section aria-labelledby="jd-heading" className="ai-card p-5 space-y-3">
          <div className="flex items-baseline justify-between gap-2">
            <div>
              <h2 id="jd-heading" className="text-sm font-semibold text-white">2 · Job description</h2>
              <p className="text-xs text-slate-400 mt-0.5">Requirements, thresholds, and preferences.</p>
            </div>
            <span className="text-xs text-slate-400 tabular-nums shrink-0">{jobText.length} chars</span>
          </div>
          <label className="block">
            <span className="text-xs font-semibold text-slate-300">Job title</span>
            <input
              className="ai-input mt-1 px-3 py-2"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              placeholder="e.g. ML Engineer"
            />
          </label>
          <UploadZone
            label="Upload job description file"
            accept=".pdf,.docx,.txt"
            fileName={jobFile}
            loading={parsing === 'job_description'}
            hint="PDF, DOCX, or TXT"
            onFile={(f) => fileToText(f, 'job_description')}
            onClear={() => { setJobFile(''); setJobText(''); }}
          />
          <label className="block">
            <span className="sr-only">Job description text</span>
            <textarea
              className="ai-input h-44 p-3 leading-6"
              placeholder="Paste job description…"
              value={jobText}
              onChange={(e) => setJobText(e.target.value)}
            />
          </label>
          <p className="text-xs text-slate-400">Mandatory vs. preferred and year thresholds are detected automatically.</p>
        </section>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          disabled={!canSubmit}
          onClick={submit}
          aria-busy={busy}
          className="ai-btn-primary px-6 py-2.5 text-sm min-w-[200px]"
        >
          {busy ? 'Analyzing…' : parsing ? 'Extracting text…' : 'Analyze job fit'}
        </button>
        {!canSubmit && !busy && (
          <span className="text-sm text-slate-400">Add both resume and job description text to continue.</span>
        )}
      </div>
    </div>
  );
}
