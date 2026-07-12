import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from 'recharts'
import type { ResearchData } from '../types'
import { METRIC_HELP, exportCsv, fmtPct } from '../utils'
import { Tooltip } from '../components/Tooltip'

const PIE_COLORS = ['#d4a843', '#60a5fa', '#34d399', '#a78bfa', '#f87171', '#94a3b8', '#fbbf24', '#38bdf8', '#c084fc', '#4ade80']

interface PortfolioInstitutionalProps {
  research: ResearchData
}

export function PortfolioInstitutional({ research }: PortfolioInstitutionalProps) {
  const { portfolio_analytics: pa } = research
  const { positions, analytics, method, as_of: asOf } = pa

  if (!positions.length) {
    return (
      <div className="workspace">
        <div className="workspace-head">
          <h2 className="workspace-title">Portfolio</h2>
        </div>
        <div className="card empty-state">
          <p>No portfolio recommendations.</p>
          <p className="empty-hint">Run pipeline to generate HRP-optimized allocations.</p>
        </div>
      </div>
    )
  }

  const chartData = positions.map((p) => ({
    name: p.ticker,
    weight: Math.round(p.weight * 1000) / 10,
  }))

  const handleExport = () => {
    exportCsv(
      `pmip_portfolio_${asOf}.csv`,
      positions.map((p) => ({
        rank: p.rank,
        ticker: p.ticker,
        weight: p.weight,
        expected_alpha: p.expected_alpha,
        tier: p.tier,
        method,
      })),
    )
  }

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Portfolio Construction</h2>
          <p className="workspace-sub">
            {method.toUpperCase()} allocation · as of {asOf}
          </p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={handleExport}>Export CSV</button>
      </div>

      <div className="kpi-row">
        <Kpi label="Positions" value={String(analytics.n_positions)} />
        <Kpi label="Exp α (10d)" value={`${(analytics.expected_alpha_10d * 100).toFixed(2)}%`} />
        <Kpi label="Ann. Vol" value={analytics.annualized_vol != null ? `${(analytics.annualized_vol * 100).toFixed(1)}%` : '—'} />
        <Kpi label="Implied Sharpe" value={analytics.implied_sharpe != null ? analytics.implied_sharpe.toFixed(2) : '—'} help={METRIC_HELP.sharpe} />
        <Kpi label="Effective N" value={analytics.effective_n.toFixed(1)} help={METRIC_HELP.effective_n} />
        <Kpi label="HHI" value={analytics.hhi.toFixed(3)} help={METRIC_HELP.hhi} />
        <Kpi label="Top-3 wt" value={fmtPct(analytics.top3_concentration, 0)} />
      </div>

      <div className="portfolio-layout">
        <div className="card portfolio-chart-card">
          <div className="card-title">Allocation · {method.toUpperCase()}</div>
          <div className="pie-wrap">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={chartData} dataKey="weight" nameKey="name" cx="50%" cy="50%" innerRadius={65} outerRadius={100} paddingAngle={2}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <RechartsTooltip contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8 }} formatter={(v: number) => [`${v}%`, 'Weight']} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="tier-exposure">
            <div className="card-title">Tier Exposure</div>
            {Object.entries(analytics.tier_exposure).map(([tier, wt]) => (
              <div key={tier} className="tier-bar-row">
                <span className="tier-bar-label">{tier}</span>
                <div className="tier-bar-track">
                  <div className="tier-bar-fill" style={{ width: `${wt * 100}%` }} />
                </div>
                <span className="mono">{fmtPct(wt, 0)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Holdings</div>
          <div className="holdings-list">
            {positions.map((p) => (
              <div key={p.rank} className="holding-item">
                <span className="miner-rank">{p.rank}</span>
                <div className="holding-info">
                  <span className="holding-ticker">{p.ticker}</span>
                  <span className="tier-badge">{p.tier}</span>
                  <div className="holding-bar">
                    <div className="holding-bar-fill" style={{ width: `${p.weight * 100}%` }} />
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
    </div>
  )
}

function Kpi({ label, value, help }: { label: string; value: string; help?: string }) {
  return (
    <div className="kpi-card">
      {help ? <Tooltip label={help}><span className="kpi-label">{label}</span></Tooltip> : <span className="kpi-label">{label}</span>}
      <span className="kpi-value">{value}</span>
    </div>
  )
}
