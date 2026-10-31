import { ColumnGuide } from '../components/ColumnGuide'
import type { ResearchData } from '../types'
import { METRIC_HELP, fmtPct } from '../utils'
import { Tooltip } from '../components/Tooltip'

interface ModelValidationProps {
  research: ResearchData
  onOpenPipeline?: () => void
}

export function ModelValidation({ research, onOpenPipeline }: ModelValidationProps) {
  const { model_catalog: models, model_summary: summary, purged_evidence: evidence, integrity } = research

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Model Validation</h2>
          <p className="workspace-sub">Cite the purged table · operational catalog is secondary · history/paper use as-of scores</p>
        </div>
      </div>

      {!evidence && (
        <div className="card empty-state" style={{ marginBottom: '1.25rem' }}>
          <p>No purged research table yet.</p>
          <p className="empty-hint">Run <code>make research</code> (or the research stage) to write docs/research/results.json.</p>
          {onOpenPipeline ? (
            <button type="button" className="btn btn-sm" onClick={onOpenPipeline} style={{ marginTop: '0.75rem' }}>
              Run pipeline
            </button>
          ) : null}
        </div>
      )}

      {evidence && (
        <section className="method-note" aria-label="Purged evidence to cite">
          <h3>Evidence to cite</h3>
          <p className="explain-intro">{evidence.note}</p>
          <p className="row-sub">
            Generated {evidence.generated_at?.slice(0, 10)} · {evidence.horizon_days}d horizon · {evidence.cost_bps} bps flip cost
            {integrity ? ` · history/paper = ${integrity.history_scoring}` : ''}
          </p>
          <div className="table-wrap" style={{ marginTop: '0.75rem' }}>
            <table className="data-table institutional">
              <thead>
                <tr>
                  <th>Study</th>
                  <th className="num">OOS dates</th>
                  <th className="num">HGB AUC</th>
                  <th className="num">HGB acc</th>
                  <th>Best book (after cost)</th>
                </tr>
              </thead>
              <tbody>
                {evidence.studies.map((study) => {
                  const best = [...study.books]
                    .filter((b) => b.total_return != null)
                    .sort((a, b) => (b.total_return ?? 0) - (a.total_return ?? 0))[0]
                  return (
                    <tr key={study.name}>
                      <td>
                        <span className="mono gold-text">{study.name}</span>
                        <span className="row-sub">{study.question}</span>
                      </td>
                      <td className="num mono">{study.n_oos}</td>
                      <td className="num mono">{study.auc != null ? study.auc.toFixed(3) : '—'}</td>
                      <td className="num mono">{study.accuracy != null ? fmtPct(study.accuracy, 0) : '—'}</td>
                      <td className="mono">
                        {best
                          ? `${best.name.replace(/_/g, ' ')} · ${((best.total_return ?? 0) * 100).toFixed(1)}%`
                          : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div className="kpi-row">
        <Kpi label="Models deployed" value={String(summary.n_models)} help="How many entity-and-horizon model files are saved and listed below." />
        <Kpi
          label="Mean walk-forward AUC"
          value={summary.mean_auc != null ? summary.mean_auc.toFixed(3) : '—'}
          help={METRIC_HELP.auc}
          highlight={summary.mean_auc != null && summary.mean_auc >= 0.6}
        />
        <Kpi
          label="Horizons"
          value={(summary.horizons || []).map((h) => summary.horizon_labels?.[String(h)] ?? `${h}d`).join(' · ') || '—'}
          help={METRIC_HELP.horizon}
        />
        <Kpi label="Backend" value={summary.backends.join(', ') || '—'} help={METRIC_HELP.backend} />
      </div>

      <ColumnGuide items={[
        { term: 'Walk-forward AUC', text: METRIC_HELP.auc },
        { term: 'Walk-forward accuracy', text: METRIC_HELP.accuracy },
        { term: 'Folds', text: METRIC_HELP.folds },
        { term: 'Latest P', text: METRIC_HELP.latestP },
        { term: 'Horizon', text: METRIC_HELP.horizon },
        { term: 'Model', text: METRIC_HELP.model },
      ]} />

      <div className="card table-card">
        <div className="card-title">Model Catalog</div>
        <div className="table-wrap">
          <table className="data-table institutional">
            <thead>
              <tr>
                <th><Tooltip label={METRIC_HELP.entity}><span>Entity</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.horizon}><span>Horizon</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.backend}><span>Backend</span></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.features}><span>Features</span></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.auc}><span>WF AUC</span></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.accuracy}><span>WF Acc</span></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.folds}><span>Folds</span></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.latestP}><span>Latest P</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.trained}><span>Trained</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.status}><span>Status</span></Tooltip></th>
              </tr>
            </thead>
            <tbody>
              {models.length === 0 ? (
                <tr>
                  <td colSpan={10} className="empty-row">
                    No models in registry.{' '}
                    {onOpenPipeline ? (
                      <button type="button" className="btn btn-sm" onClick={onOpenPipeline}>Run pipeline</button>
                    ) : (
                      'Run pipeline.'
                    )}
                  </td>
                </tr>
              ) : (
                models.map((m) => (
                  <tr key={`${m.entity}-${m.horizon_days}`}>
                    <td>
                      <span className="mono gold-text">{m.entity}</span>
                      <span className="row-sub">{m.label}</span>
                    </td>
                    <td className="mono">{summary.horizon_labels?.[String(m.horizon_days)] ?? `${m.horizon_days}d`}</td>
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
            title="Purged evidence"
            text="Gold budget and miner sleeve studies use embargo = horizon, non-overlapping test days, and a 10 bp flip cost. That table is what to cite."
          />
          <MethodBlock
            title="As-of history / paper"
            text="History charts and paper books refit at each score date with a horizon embargo. Live signals still use the full-sample registry models."
          />
          <MethodBlock
            title="Operational catalog"
            text="The rows below are the deployed entity×horizon files and their walk-forward diagnostics. Useful for lineage; not the economic proof."
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
