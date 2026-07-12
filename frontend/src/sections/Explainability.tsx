import { useState } from 'react'
import type { DashboardData, ExplainData } from '../types'
import { fmtPct, signalClass } from '../utils'

interface ExplainabilityProps {
  explain: ExplainData
  dashboard: DashboardData
}

export function Explainability({ explain, dashboard }: ExplainabilityProps) {
  const [expandedStep, setExpandedStep] = useState<string | null>(explain.pipeline[0]?.id ?? null)

  return (
    <div className="workspace explain-workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">How It Works</h2>
          <p className="workspace-subtitle">
            End-to-end transparency — every step from raw market data to tradeable signals, in plain language
          </p>
        </div>
      </div>

      <div className="explain-banner">
        <span className="explain-banner-icon" aria-hidden>◎</span>
        <p>{explain.transparency_note}</p>
      </div>

      {explain.signal_walkthrough && (
        <div className="card walkthrough-card">
          <div className="card-title">Example — How a signal is produced</div>
          <div className="walkthrough-head">
            <div>
              <span className="walkthrough-entity">{explain.signal_walkthrough.label}</span>
              <span className="mono walkthrough-ticker">{explain.signal_walkthrough.entity}</span>
            </div>
            <span className={`signal-badge lg ${signalClass(explain.signal_walkthrough.signal)}`}>
              {explain.signal_walkthrough.signal}
            </span>
            <span className="walkthrough-horizon">{explain.signal_walkthrough.horizon_days}d horizon</span>
          </div>
          <ol className="walkthrough-steps">
            {explain.signal_walkthrough.steps.map((s, i) => (
              <li key={i}>
                <span className="walk-step-num">{i + 1}</span>
                <div>
                  <strong>{s.step}</strong>
                  <p>{s.detail.replace(/\*\*/g, '')}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="card">
        <div className="card-title">The 7-Step Pipeline</div>
        <p className="explain-intro">
          Click each step to see what happens, why it matters, and live status from your database (as of {explain.as_of}).
        </p>
        <div className="pipeline-flow">
          {explain.pipeline.map((step, idx) => {
            const open = expandedStep === step.id
            const status = step.live?.status ?? 'pending'
            return (
              <div key={step.id} className={`pipeline-step ${open ? 'open' : ''} ${status}`}>
                <button
                  type="button"
                  className="pipeline-step-head"
                  onClick={() => setExpandedStep(open ? null : step.id)}
                  aria-expanded={open}
                >
                  <span className="pipeline-step-num">{idx + 1}</span>
                  <span className="pipeline-step-title">{step.title.replace(/^\d+\.\s*/, '')}</span>
                  <span className={`pipeline-status ${status}`}>{status}</span>
                  <span className="pipeline-chevron" aria-hidden>{open ? '▾' : '▸'}</span>
                </button>
                {open && (
                  <div className="pipeline-step-body">
                    <div className="explain-block">
                      <span className="explain-label">In plain English</span>
                      <p>{step.plain}</p>
                    </div>
                    <div className="explain-block">
                      <span className="explain-label">Technical detail</span>
                      <p className="technical">{step.technical}</p>
                    </div>
                    <div className="explain-block">
                      <span className="explain-label">Outputs</span>
                      <div className="tag-row">
                        {step.outputs.map((o) => <span key={o} className="tag">{o}</span>)}
                      </div>
                    </div>
                    {step.live?.metrics && (
                      <div className="explain-block">
                        <span className="explain-label">Live metrics</span>
                        <div className="metrics-grid">
                          {Object.entries(step.live.metrics).map(([k, v]) => (
                            <div key={k} className="metric-chip">
                              <span className="metric-chip-k">{k.replace(/_/g, ' ')}</span>
                              <span className="metric-chip-v">{v == null ? '—' : String(v)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-title">Signal Labels — What They Mean</div>
          <table className="data-table institutional compact">
            <thead>
              <tr>
                <th>Label</th>
                <th>Rule</th>
                <th>Interpretation</th>
              </tr>
            </thead>
            <tbody>
              {explain.signal_rules.map((r) => (
                <tr key={r.signal}>
                  <td><span className={`signal-badge ${signalClass(r.signal)}`}>{r.signal}</span></td>
                  <td className="rule-cell">{r.condition}</td>
                  <td className="meaning-cell">{r.meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="card-title">Gold Outlook — Plain Explanation</div>
          <div className="plain-metric">
            <span className="plain-metric-value gold-text">{explain.gold_outlook_explanation.bullish_pct}%</span>
            <span className="plain-metric-label">bullish probability</span>
          </div>
          <p className="explain-text">{explain.gold_outlook_explanation.plain}</p>
          <div className="macro-inputs">
            <span className="explain-label">Inputs used today</span>
            <div className="metrics-grid">
              {Object.entries(explain.macro_inputs).map(([k, v]) => (
                <div key={k} className="metric-chip">
                  <span className="metric-chip-k">{k.replace(/_/g, ' ')}</span>
                  <span className="metric-chip-v">{v == null ? '—' : String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">
          Causal Chain — Why Macro Matters for Gold &amp; Miners
          <span className="graph-meta">
            {explain.knowledge_graph_size.nodes} nodes · {explain.knowledge_graph_size.edges} hypotheses
          </span>
        </div>
        <div className="causal-flow">
          {explain.causal_chain.map((edge, i) => (
            <div key={i} className="causal-item">
              <div className="causal-nodes">
                <span className="causal-source">{edge.source}</span>
                <span className={`causal-arrow ${edge.direction}`}>
                  {edge.direction === 'negative' ? '−→' : '→'}
                </span>
                <span className="causal-target">{edge.target}</span>
                <span className={`evidence-chip ${edge.evidence_strength}`}>{edge.evidence_strength}</span>
              </div>
              <p className="causal-hypothesis">{edge.hypothesis}</p>
              {edge.magnitude_hint && (
                <span className="causal-magnitude">Magnitude: {edge.magnitude_hint}</span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-title">Research Agents — Reasoning &amp; Evidence</div>
        <p className="explain-intro">
          Four agents score macro, geopolitical, mining fundamental, and quant model context. Each explains its conclusion in plain language.
        </p>
        <div className="agent-explain-grid">
          {explain.agents.map((agent) => (
            <div key={agent.name} className="agent-explain-card">
              <div className="agent-explain-head">
                <span className="agent-explain-name">{agent.name.replace('Agent', '')}</span>
                <span className="agent-explain-conf">{(agent.confidence * 100).toFixed(0)}% conf.</span>
              </div>
              <p className="agent-explain-summary">{agent.summary}</p>
              {agent.signals.length > 0 && (
                <ul className="agent-signal-list">
                  {agent.signals.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              )}
              <div className="agent-score-pills">
                {Object.entries(agent.scores).slice(0, 3).map(([k, v]) => (
                  <span key={k} className="score-pill">
                    {k.replace(/_/g, ' ')}: {typeof v === 'number' && v <= 1 ? fmtPct(v, 0) : v}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-title">Features the Models See</div>
          <p className="explain-intro">
            Models do not use raw prices directly — they use engineered features grouped below.
          </p>
          {explain.feature_families.map((fam) => (
            <div key={fam.name} className="feature-family">
              <div className="feature-family-name">{fam.name}</div>
              <p className="feature-family-why">{fam.why}</p>
              <div className="tag-row">
                {fam.examples.map((ex) => <span key={ex} className="tag mono">{ex}</span>)}
              </div>
            </div>
          ))}
          {explain.sample_features.length > 0 && (
            <div className="sample-features">
              <span className="explain-label">Sample from live GLD model</span>
              <div className="tag-row">
                {explain.sample_features.map((f) => <span key={f} className="tag mono sm">{f}</span>)}
              </div>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-title">Data Sources</div>
          <table className="data-table institutional compact">
            <thead>
              <tr><th>Data</th><th>Source</th><th>Freq</th></tr>
            </thead>
            <tbody>
              {explain.data_sources.map((ds) => (
                <tr key={ds.name}>
                  <td>{ds.name}</td>
                  <td>{ds.source}</td>
                  <td>{ds.frequency}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="regime-plain" style={{ marginTop: '1.25rem' }}>
            <div className="card-title">Regime Detection</div>
            <p className="explain-text">{explain.regime_explanation.how_it_works}</p>
            {dashboard.regime && (
              <div className="regime-current-plain">
                <strong>Today:</strong> {dashboard.regime.regime_name} ·{' '}
                {(dashboard.regime.confidence * 100).toFixed(0)}% confidence ·{' '}
                Gold {dashboard.regime.gold_bias}, miners {dashboard.regime.miner_bias}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
