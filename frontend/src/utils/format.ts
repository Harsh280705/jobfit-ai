export function pct(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  return `${n}%`;
}

export function shortId(id: string): string {
  return id ? `${id.slice(0, 8)}…` : '';
}
