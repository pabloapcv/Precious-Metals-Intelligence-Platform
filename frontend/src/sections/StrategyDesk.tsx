import { useMemo, useState } from 'react'
import type { StrategyData, StrategyPlaybook } from '../types'
import { fmtPct } from '../utils'

interface StrategyDeskProps {
  strategies: StrategyData
  onOpenPipeline?: () => void
}

const TAG_LABEL: Record<string, string> = {
  constructive: 'Constructive',
  neutral: 'Neutral',
  defensive: 'Defensive',
}

function pctBudget(n: number) {
  return `${Math.round(n * 100)}%`
}

function PlaybookCard({
  playbook,
  primary,
  selected,
  onSelect,
}: {
  playbook: StrategyPlaybook
  primary: boolean
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={`strategy-card tag-${playbook.tag} ${primary ? 'primary' : ''} ${selected ? 'selected' : ''}`}
      onClick={onSelect}
    >
      <div className="strategy-card-top">
        <span className="strategy-card-title">{playbook.title}</span>
        <span className={`strategy-tag tag-${playbook.tag}`}>{TAG_LABEL[playbook.tag] ?? playbook.tag}</span>
      </div>
      <p className="strategy-card-action">{playbook.action}</p>
      <div className="strategy-card-meta">
        <span className="mono">{playbook.horizon_label}</span>
        <span className="mono">gold {pctBudget(playbook.gold_budget)}</span>
        <span className="mono">conf {fmtPct(playbook.confidence, 0)}</span>
        {primary && <span className="strategy-primary-chip">Primary</span>}
      </div>
    </button>
  )
}

export function StrategyDesk({ strategies, onOpenPipeline }: StrategyDeskProps) {
  const primaryId = strategies.primary
  const [selectedId, setSelectedId] = useState(primaryId ?? strategies.strategies[0]?.id)
  const selected =
    strategies.strategies.find((s) => s.id === selectedId) ??
    strategies.strategies.find((s) => s.id === primaryId) ??
    strategies.strategies[0]

  const drivers = strategies.drivers
  const sleeveLine = useMemo(() => {
    if (!selected?.sleeve?.length) return '—'
    return selected.sleeve.map((s) => `${s.entity} ${pctBudget(s.weight)}`).join(' · ')
  }, [selected])

  if (!strategies.strategies.length) {
    return (
      <div className="workspace">
        <div className="empty-state">
          <p>No strategy playbooks yet.</p>
          <p className="empty-hint">Run the pipeline so allocation, signals, and paper books can compose suggestions.</p>
          {onOpenPipeline ? (
            <button type="button" className="btn btn-sm" onClick={onOpenPipeline} style={{ marginTop: '0.75rem' }}>
              Run pipeline
            </button>
          ) : null}
        </div>
      </div>
    )
  }

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Strategy Desk</h2>
          <p className="workspace-sub">
            Ranked playbooks from today’s stance, <span className="source-badge live">live</span> signal
            sleeve, regime, and <span className="source-badge asof">as-of</span> paper paths.
            {strategies.as_of ? ` As of ${strategies.as_of}.` : ''}
          </p>
        </div>
      </div>

      <section className="method-note" aria-label="How strategies are suggested">
        <h3>How these suggestions are built</h3>
        <p className="explain-intro">{strategies.note}</p>
        <p className="explain-intro">
          Sleeve names come from the live full-sample signal book (10d long/OW ≤8). Horizon ranking and
          paper evidence use purged as-of scores. Do not treat the primary playbook as a purged track record.
        </p>
      </section>

      <div className="kpi-row">
        <div className="kpi-card">
          <span className="kpi-label">Gold stance</span>
          <span className="kpi-value">{drivers.stance}</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Gold budget</span>
          <span className="kpi-value">{pctBudget(drivers.gold_budget)}</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Regime</span>
          <span className="kpi-value">{drivers.regime_name ?? '—'}</span>
          <span className="row-sub">gold bias {drivers.gold_bias}</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Long / OW signals</span>
          <span className="kpi-value">{drivers.n_long_signals}</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Best paper</span>
          <span className="kpi-value">
            {drivers.best_paper_horizon != null ? `${drivers.best_paper_horizon}d` : '—'}
          </span>
          <span className="row-sub">
            {drivers.best_paper_return != null ? fmtPct(drivers.best_paper_return, 1) : 'no path yet'}
          </span>
        </div>
      </div>

      <div className="strategy-layout">
        <div className="strategy-list" role="list">
          {strategies.strategies.map((playbook) => (
            <PlaybookCard
              key={playbook.id}
              playbook={playbook}
              primary={playbook.id === primaryId}
              selected={playbook.id === selected?.id}
              onSelect={() => setSelectedId(playbook.id)}
            />
          ))}
        </div>

        {selected && (
          <article className={`strategy-detail tag-${selected.tag}`}>
            <div className="strategy-detail-head">
              <div>
                <h3>{selected.title}</h3>
                <p>{selected.action}</p>
              </div>
              <span className={`strategy-tag tag-${selected.tag}`}>{TAG_LABEL[selected.tag] ?? selected.tag}</span>
            </div>

            <div className="strategy-recipe">
              <div className="strategy-recipe-row">
                <span className="kpi-label">Horizon</span>
                <span className="mono">{selected.horizon_label} ({selected.horizon_days}d)</span>
              </div>
              <div className="strategy-recipe-row">
                <span className="kpi-label">Gold budget</span>
                <span className="mono">{pctBudget(selected.gold_budget)}</span>
              </div>
              <div className="strategy-recipe-row">
                <span className="kpi-label">Residual</span>
                <span className="mono">
                  {selected.residual.label} {pctBudget(selected.residual.weight)}
                </span>
              </div>
              <div className="strategy-recipe-row">
                <span className="kpi-label">Confidence</span>
                <span className="mono">{fmtPct(selected.confidence, 0)}</span>
              </div>
              <div className="strategy-recipe-row stack">
                <span className="kpi-label">Sleeve</span>
                <span className="mono strategy-sleeve-line">{sleeveLine}</span>
              </div>
            </div>

            <div className="strategy-block">
              <h4>Evidence</h4>
              <ul>
                {(selected.evidence || []).filter(Boolean).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>

            <div className="strategy-block">
              <h4>Caveats</h4>
              <ul>
                {(selected.caveats || []).filter(Boolean).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          </article>
        )}
      </div>
    </div>
  )
}
