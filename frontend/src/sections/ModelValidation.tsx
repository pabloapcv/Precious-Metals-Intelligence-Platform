import type { ResearchData } from '../types'
import { METRIC_HELP, fmtPct } from '../utils'
import { Tooltip } from '../components/Tooltip'

interface ModelValidationProps {
  research: ResearchData
}

export function ModelValidation({ research }: ModelValidationProps) {
  const { model_catalog: models, model_summary: summary } = research

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Model Validation</h2>
          <p className="workspace-sub">Walk-forward classifier performance · model lineage · prediction freshness</p>
        </div>
      </div>

      <div className="kpi-row">
        <Kpi label="Models deployed" value={String(summary.n_models)} />
        <Kpi
          label="Mean walk-forward AUC"
          value={summary.mean_auc != null ? summary.mean_auc.toFixed(3) : '—'}
          help={METRIC_HELP.auc}
          highlight={summary.mean_auc != null && summary.mean_auc >= 0.6}
        />
        <Kpi label="Horizons" value={summary.horizons.join(' / ') + 'd'} />
        <Kpi label="Backend" value={summary.backends.join(', ') || '—'} />
      </div>

      <div className="card table-card">
        <div className="card-title">Model Catalog</div>
        <div className="table-wrap">
          <table className="data-table institutional">
            <thead>
              <tr>
                <th>Entity</th>
                <th>Horizon</th>
                <th>Backend</th>
                <th className="num">Features</th>
                <th className="num"><Tooltip label={METRIC_HELP.auc}><span>WF AUC</span></Tooltip></th>
                <th className="num">WF Acc</th>
                <th className="num">Folds</th>
                <th className="num">Latest P</th>
                <th>Trained</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {models.length === 0 ? (
                <tr><td colSpan={10} className="empty-row">No models in registry — run pipeline.</td></tr>
              ) : (
                models.map((m) => (
                  <tr key={`${m.entity}-${m.horizon_days}`}>
                    <td>
                      <span className="mono gold-text">{m.entity}</span>
                      <span className="row-sub">{m.label}</span>
                    </td>
                    <td className="mono">{m.horizon_days}d</td>
                    <td>{m.backend}</td>
                    <td className="num mono">{m.n_features}</td>
                    <td className={`num mono ${m.walk_forward.mean_auc != null && m.walk_forward.mean_auc >= 0.6 ? 'positive-text' : ''}`}>
                      {m.walk_forward.mean_auc != null ? m.walk_forward.mean_auc.toFixed(3) : '—'}
                    </td>
                    <td className="num mono">
                      {m.walk_forward.mean_accuracy != null ? fmtPct(m.walk_forward.mean_accuracy, 0) : '—'}
                    </td>
                    <td className="num mono">{m.walk_forward.folds || '—'}</td>
                    <td className="num mono">
                      {m.latest_prob != null ? fmtPct(m.latest_prob, 0) : '—'}
                    </td>
                    <td className="model-ver">{m.trained_at ?? m.latest_prediction_date ?? '—'}</td>
                    <td>
                      <span className={`status-chip ${m.walk_forward.status === 'ok' || m.walk_forward.folds > 0 ? 'ok' : 'pending'}`}>
                        {m.walk_forward.folds > 0 ? 'validated' : m.walk_forward.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card methodology-card">
        <div className="card-title">Methodology</div>
        <div className="method-grid">
          <MethodBlock
            title="Walk-forward validation"
            text="252d train / 42d test / 21d step. Targets: P(outperform gold), P(beat GDX), forward return."
          />
          <MethodBlock
            title="Feature store"
            text="Technical, cross-asset, and macro surprise features aligned to prediction date. No lookahead."
          />
          <MethodBlock
            title="Regime conditioning"
            text="HMM regime detection on macro state vector — used for agent scoring and hypothesis context."
          />
        </div>
      </div>
    </div>
  )
}

function Kpi({
  label,
  value,
  help,
  highlight,
}: {
  label: string
  value: string
  help?: string
  highlight?: boolean
}) {
  return (
    <div className="kpi-card">
      {help ? (
        <Tooltip label={help}><span className="kpi-label">{label}</span></Tooltip>
      ) : (
        <span className="kpi-label">{label}</span>
      )}
      <span className={`kpi-value ${highlight ? 'highlight' : ''}`}>{value}</span>
    </div>
  )
}

function MethodBlock({ title, text }: { title: string; text: string }) {
  return (
    <div className="method-block">
      <div className="method-title">{title}</div>
      <p>{text}</p>
    </div>
  )
}
