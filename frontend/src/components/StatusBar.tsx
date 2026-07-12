import type { DashboardData, ResearchData } from '../types'

interface StatusBarProps {
  dashboard: DashboardData
  research: ResearchData | null
}

export function StatusBar({ dashboard, research }: StatusBarProps) {
  const summary = research?.model_summary
  const analytics = research?.portfolio_analytics?.analytics

  return (
    <div className="status-bar" role="status">
      <div className="status-group">
        <StatusItem label="Data" value={`${dashboard.data_status.macro_rows.toLocaleString()} bars`} />
        <StatusItem label="Models" value={`${summary?.n_models ?? dashboard.data_status.predictions}`} />
        <StatusItem
          label="Mean AUC"
          value={summary?.mean_auc != null ? summary.mean_auc.toFixed(3) : '—'}
          highlight={summary?.mean_auc != null && summary.mean_auc >= 0.6}
        />
        <StatusItem label="Regime" value={dashboard.regime?.regime_name ?? '—'} />
        <StatusItem label="Gold" value={`${dashboard.gold.bullish_pct}% bull`} />
      </div>
      <div className="status-group">
        {analytics && (
          <>
            <StatusItem label="Eff. N" value={analytics.effective_n.toFixed(1)} />
            <StatusItem label="Exp α" value={`${(analytics.expected_alpha_10d * 100).toFixed(2)}%`} />
          </>
        )}
        <StatusItem label="Backend" value={summary?.backends?.join(', ') ?? '—'} />
        <span className={`status-pill ${dashboard.data_status.pipeline_needed ? 'warn' : 'ok'}`}>
          {dashboard.data_status.pipeline_needed ? 'Stale' : 'Live'}
        </span>
      </div>
    </div>
  )
}

function StatusItem({
  label,
  value,
  highlight,
}: {
  label: string
  value: string
  highlight?: boolean
}) {
  return (
    <div className="status-item">
      <span className="status-k">{label}</span>
      <span className={`status-v ${highlight ? 'highlight' : ''}`}>{value}</span>
    </div>
  )
}
