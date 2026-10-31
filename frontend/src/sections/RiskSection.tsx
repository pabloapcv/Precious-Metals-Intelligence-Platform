import { Tooltip } from '../components/Tooltip'
import type { DashboardData } from '../types'
import { METRIC_HELP, fmt, signalClass } from '../utils'

interface RiskSectionProps {
  risk: DashboardData['risk']
  etfFlows: DashboardData['etf_flows']
  centralBanks: DashboardData['central_banks']
  agentScores: DashboardData['agent_scores']
}

const RISK_LABELS: Record<string, string> = {
  war_probability: 'War flag',
  oil_disruption: 'Oil disruption',
  central_bank_buying: 'Central bank buying',
  etf_flows: 'ETF flows',
}

const RISK_HELP: Record<string, string> = {
  war_probability: METRIC_HELP.gpr,
  oil_disruption: METRIC_HELP.oilDisruption,
  central_bank_buying: METRIC_HELP.cbBuying,
  etf_flows: METRIC_HELP.etfFlow,
}

export function RiskSection({ risk, etfFlows, centralBanks, agentScores }: RiskSectionProps) {
  const riskItems = Object.entries(risk).filter(([k]) => !['gpr_index', 'conflict_intensity'].includes(k))

  return (
    <div className="risk-panel">
      <div className="section-head">
        <div>
          <h2 className="section-title">Risk & Flows</h2>
          <p className="section-subtitle">Geopolitical, liquidity, and institutional demand signals</p>
        </div>
      </div>

      <div className="grid grid-3">
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              Risk Monitor
              <Tooltip label={METRIC_HELP.sourceProxy}>
                <span className="source-badge proxy">proxy</span>
              </Tooltip>
            </div>
            <Tooltip label={METRIC_HELP.gpr}>
              <span className="help-label">Signal glossary</span>
            </Tooltip>
          </div>
          <div className="risk-grid">
            {riskItems.map(([key, val]) => (
              <div key={key} className="risk-card">
                <Tooltip label={RISK_HELP[key] || METRIC_HELP.gpr}>
                  <span className="risk-label">{RISK_LABELS[key] || key.replace(/_/g, ' ')}</span>
                </Tooltip>
                <span className={`risk-badge ${signalClass(String(val))}`}>{String(val)}</span>
              </div>
            ))}
          </div>
          <div className="risk-metrics">
            <div className="risk-metric">
              <Tooltip label={METRIC_HELP.gpr}>
                <span className="label">GPR Index</span>
              </Tooltip>
              <span className="value gold-text">{fmt(risk.gpr_index as number)}</span>
            </div>
            <div className="risk-metric">
              <Tooltip label={METRIC_HELP.conflict}><span className="label">Conflict intensity</span></Tooltip>
              <span className="value">{fmt(risk.conflict_intensity as number)}</span>
            </div>
          </div>
          <p className="empty-hint" style={{ marginTop: '0.75rem' }}>
            GPR is a VIX/oil market proxy — not live news NLP.
          </p>
        </div>

        <div className="card">
          <div className="card-title">
            ETF Flows (GLD / IAU)
            <Tooltip label={METRIC_HELP.sourceEstimate}>
              <span className="source-badge estimate">estimate</span>
            </Tooltip>
          </div>
          <div className="flow-stats">
            <FlowStat label="GLD daily" value={`${fmt(etfFlows.gld_daily_m as number, 1)}M`} help={METRIC_HELP.etfFlow} />
            <FlowStat label="GLD 30d avg" value={`${fmt(etfFlows.gld_30d_avg_m as number, 1)}M`} help="Average of the estimated daily GLD flow over the last 30 observations, in millions of dollars." />
            <FlowStat label="IAU daily" value={`${fmt(etfFlows.iau_daily_m as number, 1)}M`} help="Estimated daily flow into the IAU gold trust, in millions of dollars." />
            <FlowStat
              label="Signal"
              value={String(etfFlows.signal)}
              highlight={signalClass(String(etfFlows.signal))}
              help={METRIC_HELP.etfFlow}
            />
          </div>
        </div>

        <div className="card">
          <div className="card-title">
            <Tooltip label={METRIC_HELP.cbBuying}><span>Central Bank Buying</span></Tooltip>
            <Tooltip label={METRIC_HELP.sourceSeed}>
              <span className="source-badge seed">seed</span>
            </Tooltip>
          </div>
          <div className="metric-value gold" style={{ fontSize: '1.75rem' }}>
            {fmt(centralBanks.recent_purchases_tonnes, 0)}t
          </div>
          <Tooltip label={METRIC_HELP.cbTonnes}><div className="metric-label">Recent monthly purchases</div></Tooltip>
          <ul className="cb-list">
            {centralBanks.top_buyers.map((b) => (
              <li key={b.country}>
                <span>{b.country}</span>
                <span className="mono">{b.tonnes}t</span>
              </li>
            ))}
          </ul>
          <div className={`cb-signal ${signalClass(centralBanks.signal)}`}>
            Signal: {centralBanks.signal}
          </div>
        </div>
      </div>

      <AgentPanel agentScores={agentScores} />
    </div>
  )
}

function FlowStat({
  label,
  value,
  highlight,
  help,
}: {
  label: string
  value: string
  highlight?: string
  help?: string
}) {
  return (
    <div className="flow-stat">
      {help ? <Tooltip label={help}><span className="label">{label}</span></Tooltip> : <span className="label">{label}</span>}
      <span className={`value ${highlight || ''}`}>{value}</span>
    </div>
  )
}

function AgentPanel({ agentScores }: { agentScores: DashboardData['agent_scores'] }) {
  const items = Object.entries(agentScores).flatMap(([agent, scores]) =>
    Object.entries(scores).slice(0, 2).map(([key, val]) => ({
      name: `${agent.replace('Agent', '')} · ${key.replace(/_/g, ' ')}`,
      score: Math.round(val * 100),
    })),
  )

  if (items.length === 0) return null

  return (
    <div className="card" style={{ marginTop: '1.25rem' }}>
      <div className="card-title">AI Agent Scores</div>
      <div className="agent-scores">
        {items.map((item) => (
          <div key={item.name} className="agent-score">
            <div className="agent-score-head">
              <span className="name">{item.name}</span>
              <span className="score">{item.score}%</span>
            </div>
            <div className="score-bar">
              <div className="score-bar-fill" style={{ width: `${item.score}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
