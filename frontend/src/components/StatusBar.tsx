import { Tooltip } from './Tooltip'
import type { DashboardData, ResearchData } from '../types'
import { METRIC_HELP } from '../utils'

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
        <StatusItem label="Data" value={`${dashboard.data_status.macro_rows.toLocaleString()} bars`} help={METRIC_HELP.dataBars} />
        <StatusItem label="Models" value={`${summary?.n_models ?? dashboard.data_status.predictions}`} help={METRIC_HELP.modelsCount} />
        <StatusItem
          label="Mean AUC"
          value={summary?.mean_auc != null ? summary.mean_auc.toFixed(3) : '—'}
          highlight={summary?.mean_auc != null && summary.mean_auc >= 0.6}
          help={METRIC_HELP.auc}
        />
        <StatusItem label="Regime" value={dashboard.regime?.regime_name ?? '—'} help={METRIC_HELP.regime} />
        <StatusItem label="P(Gold)" value={`${dashboard.gold.bullish_pct}%`} help={METRIC_HELP.prob} />
      </div>
      <div className="status-group">
        {analytics && (
          <>
            <StatusItem label="Effective N" value={analytics.effective_n.toFixed(1)} help={METRIC_HELP.effective_n} />
            <StatusItem label="Expected alpha" value={`${(analytics.expected_alpha_10d * 100).toFixed(2)}%`} help={METRIC_HELP.portAlpha} />
          </>
        )}
        <StatusItem label="Backend" value={summary?.backends?.join(', ') ?? '—'} help={METRIC_HELP.backendLive} />
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
  help,
}: {
  label: string
  value: string
  highlight?: boolean
  help?: string
}) {
  return (
    <div className="status-item">
      {help ? <Tooltip label={help}><span className="status-k">{label}</span></Tooltip> : <span className="status-k">{label}</span>}
      <span className={`status-v ${highlight ? 'highlight' : ''}`}>{value}</span>
    </div>
  )
}
