export function fmt(n: number | null | undefined, digits = 2) {
  if (n == null || Number.isNaN(n)) return '—'
  return n.toLocaleString(undefined, { maximumFractionDigits: digits })
}

export function fmtUsd(n: number | null | undefined) {
  if (n == null) return '—'
  return `$${fmt(n, n > 100 ? 0 : 2)}`
}

export function fmtPct(n: number, digits = 1) {
  return `${(n * 100).toFixed(digits)}%`
}

export function signalClass(signal: string) {
  if (['bullish', 'rising', 'long', 'overweight'].includes(signal)) return 'positive'
  if (['bearish', 'declining', 'short', 'underweight'].includes(signal)) return 'negative'
  return 'neutral'
}

export function biasClass(bias: string | undefined) {
  if (bias === 'bullish') return 'positive'
  if (bias === 'bearish') return 'negative'
  return 'neutral'
}

export function exportCsv(filename: string, rows: Record<string, unknown>[]) {
  if (rows.length === 0) return
  const headers = Object.keys(rows[0])
  const lines = [
    headers.join(','),
    ...rows.map((row) =>
      headers.map((h) => {
        const v = row[h]
        const s = v == null ? '' : String(v)
        return s.includes(',') ? `"${s}"` : s
      }).join(','),
    ),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const METRIC_HELP: Record<string, string> = {
  alpha: 'Expected excess return vs gold over the forecast horizon.',
  prob: 'Model probability that the asset outperforms gold.',
  auc: 'Walk-forward ROC-AUC — discrimination of outperformance classifier across rolling folds.',
  hhi: 'Herfindahl-Hirschman Index — portfolio concentration (lower = more diversified).',
  effective_n: 'Effective number of independent bets — 1/HHI.',
  sharpe: 'Implied Sharpe using predicted alpha proxy and realized covariance (annualized).',
  real_yields: '10-year Treasury yield minus inflation expectations. Higher real yields typically pressure gold.',
  gpr: 'Geopolitical Risk Index — elevated readings suggest elevated macro uncertainty.',
  hrp: 'Hierarchical Risk Parity — diversifies across miners while respecting correlation structure.',
  regime: 'Hidden Markov Model classification of the current macro environment.',
}

export const SERIES_LABELS: Record<string, string> = {
  'GC=F': 'Gold',
  'DX-Y.NYB': 'DXY',
  GDX: 'GDX Miners',
  US10Y_REAL: 'Real 10Y',
  VIX: 'VIX',
}

export const SERIES_COLORS: Record<string, string> = {
  'GC=F': '#d4a843',
  'DX-Y.NYB': '#60a5fa',
  GDX: '#34d399',
  US10Y_REAL: '#a78bfa',
  VIX: '#f87171',
}
