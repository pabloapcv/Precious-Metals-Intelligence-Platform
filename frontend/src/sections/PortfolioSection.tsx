import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from 'recharts'
import { Tooltip } from '../components/Tooltip'
import type { DashboardData } from '../types'
import { METRIC_HELP, fmtPct } from '../utils'

const PIE_COLORS = ['#d4a843', '#60a5fa', '#34d399', '#a78bfa', '#f87171', '#94a3b8', '#fbbf24', '#38bdf8', '#c084fc', '#4ade80']

interface PortfolioSectionProps {
  portfolio: DashboardData['portfolio']
}

export function PortfolioSection({ portfolio }: PortfolioSectionProps) {
  const chartData = portfolio.map((p) => ({
    name: p.ticker,
    weight: Math.round(p.weight * 1000) / 10,
    alpha: Math.round(p.expected_alpha * 1000) / 10,
  }))

  const totalWeight = chartData.reduce((s, p) => s + p.weight, 0)

  return (
    <section id="portfolio" className="section">
      <div className="section-head">
        <div>
          <h2 className="section-title">Portfolio Recommendations</h2>
          <p className="section-subtitle">HRP-optimized weights across top mining exposures</p>
        </div>
        <Tooltip label={METRIC_HELP.hrp}>
          <span className="help-label">About HRP</span>
        </Tooltip>
      </div>

      {portfolio.length === 0 ? (
        <div className="card empty-state">
          <p>No portfolio yet.</p>
          <p className="empty-hint">Run the pipeline to generate HRP-optimized allocations.</p>
        </div>
      ) : (
        <div className="portfolio-layout">
          <div className="card portfolio-chart-card">
            <div className="card-title">Allocation</div>
            <div className="pie-wrap">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={chartData}
                    dataKey="weight"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={70}
                    outerRadius={110}
                    paddingAngle={2}
                  >
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip
                    contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8 }}
                    formatter={(v: number, _n, props) => [
                      `${v}%`,
                      props.payload?.name ?? 'Weight',
                    ]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="pie-center">
                <span className="pie-center-value">{totalWeight.toFixed(0)}%</span>
                <span className="pie-center-label">allocated</span>
              </div>
            </div>
            <div className="legend">
              {chartData.map((p, i) => (
                <div key={p.name} className="legend-item">
                  <span className="legend-dot" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                  <span>{p.name}</span>
                  <span className="mono">{p.weight}%</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-title">Holdings Detail</div>
            <div className="holdings-list">
              {portfolio.map((p) => (
                <div key={p.rank} className="holding-item">
                  <span className="miner-rank">{p.rank}</span>
                  <div className="holding-info">
                    <span className="holding-ticker">{p.ticker}</span>
                    <div className="holding-bar">
                      <div
                        className="holding-bar-fill"
                        style={{ width: `${p.weight * 100}%` }}
                      />
                    </div>
                  </div>
                  <div className="holding-stats">
                    <span className="mono">{fmtPct(p.weight, 1)}</span>
                    <span className={`holding-alpha ${p.expected_alpha >= 0 ? 'positive-text' : 'negative-text'}`}>
                      α {fmtPct(p.expected_alpha)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
