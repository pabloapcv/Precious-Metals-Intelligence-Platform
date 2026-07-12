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
  war_probability: 'War probability',
  oil_disruption: 'Oil disruption',
  central_bank_buying: 'Central bank buying',
  etf_flows: 'ETF flows',
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
            <div className="card-title">Risk Monitor</div>
            <Tooltip label={METRIC_HELP.gpr}>
              <span className="help-label">Signal glossary</span>
            </Tooltip>
          </div>
          <div className="risk-grid">
            {riskItems.map(([key, val]) => (
              <div key={key} className="risk-card">
                <span className="risk-label">{RISK_LABELS[key] || key.replace(/_/g, ' ')}</span>
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
              <span className="label">Conflict intensity</span>
              <span className="value">{fmt(risk.conflict_intensity as number)}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-title">ETF Flows (GLD / IAU)</div>
          <div className="flow-stats">
            <FlowStat label="GLD daily" value={`${fmt(etfFlows.gld_daily_m as number, 1)}M`} />
            <FlowStat label="GLD 30d avg" value={`${fmt(etfFlows.gld_30d_avg_m as number, 1)}M`} />
            <FlowStat label="IAU daily" value={`${fmt(etfFlows.iau_daily_m as number, 1)}M`} />
            <FlowStat
              label="Signal"
              value={String(etfFlows.signal)}
              highlight={signalClass(String(etfFlows.signal))}
            />
          </div>
        </div>

        <div className="card">
          <div className="card-title">Central Bank Buying</div>
          <div className="metric-value gold" style={{ fontSize: '1.75rem' }}>
            {fmt(centralBanks.recent_purchases_tonnes, 0)}t
          </div>
          <div className="metric-label">Recent monthly purchases</div>
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
}: {
  label: string
  value: string
  highlight?: string
}) {
  return (
    <div className="flow-stat">
      <span className="label">{label}</span>
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
