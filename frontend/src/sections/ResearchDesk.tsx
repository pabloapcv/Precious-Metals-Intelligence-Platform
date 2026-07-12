import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { DashboardData, ResearchData } from '../types'
import { SERIES_COLORS, SERIES_LABELS } from '../utils'

interface ResearchDeskProps {
  dashboard: DashboardData
  research: ResearchData
}

export function ResearchDesk({ dashboard, research }: ResearchDeskProps) {
  const chartData = buildMacroChartData(research.macro_series)
  const regimeChart = research.regime_history.map((r) => ({
    date: r.date.slice(5),
    confidence: Math.round(r.confidence * 100),
    regime: r.regime_name.split(' / ')[0],
  }))

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Research Desk</h2>
          <p className="workspace-sub">Macro time series · regime transitions · causal hypotheses</p>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card chart-card">
          <div className="card-title">Macro Cross-Asset (252d)</div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis yAxisId="left" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} width={55} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} width={40} />
              <RechartsTooltip contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line yAxisId="left" type="monotone" dataKey="GC=F" name={SERIES_LABELS['GC=F']} stroke={SERIES_COLORS['GC=F']} dot={false} strokeWidth={1.5} />
              <Line yAxisId="left" type="monotone" dataKey="GDX" name={SERIES_LABELS.GDX} stroke={SERIES_COLORS.GDX} dot={false} strokeWidth={1.5} />
              <Line yAxisId="right" type="monotone" dataKey="VIX" name={SERIES_LABELS.VIX} stroke={SERIES_COLORS.VIX} dot={false} strokeWidth={1} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card chart-card">
          <div className="card-title">Regime Confidence History</div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={regimeChart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
              <RechartsTooltip contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8, fontSize: 12 }} />
              <Line type="monotone" dataKey="confidence" name="Confidence" stroke="#60a5fa" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
          {dashboard.regime && (
            <div className="chart-caption">
              Current: <strong>{dashboard.regime.regime_name}</strong> · {(dashboard.regime.confidence * 100).toFixed(0)}% confidence
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-title">Regime Definitions</div>
          <div className="regime-def-list">
            {research.regime_definitions.map((r) => (
              <div key={r.id} className="regime-def-item">
                <div className="regime-def-head">
                  <span className="regime-badge sm">{r.name}</span>
                  <span className={`bias-chip ${r.gold_bias === 'bullish' ? 'positive' : r.gold_bias === 'bearish' ? 'negative' : 'neutral'}`}>
                    Au {r.gold_bias}
                  </span>
                  <span className={`bias-chip ${r.miner_bias === 'bullish' ? 'positive' : r.miner_bias === 'bearish' ? 'negative' : 'neutral'}`}>
                    Miners {r.miner_bias}
                  </span>
                </div>
                <div className="tags">
                  {r.key_drivers.map((d) => <span key={d} className="tag">{d}</span>)}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Causal Hypotheses (Knowledge Graph)</div>
          <div className="hypothesis-list">
            {research.hypotheses.map((h, i) => (
              <div key={i} className="hypothesis-item">
                <div className="hypothesis-chain">
                  <span className="hyp-source">{h.source}</span>
                  <span className="hyp-arrow">→</span>
                  <span className="hyp-target">{h.target}</span>
                  <span className={`evidence-chip ${h.evidence_strength}`}>{h.evidence_strength}</span>
                </div>
                <p className="hypothesis-text">{h.hypothesis}</p>
                <span className="hyp-meta">{h.direction} · lag {h.lag_days}d</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function buildMacroChartData(series: ResearchData['macro_series']) {
  const dates = new Set<string>()
  Object.values(series).forEach((pts) => pts.forEach((p) => dates.add(p.date)))
  const sorted = [...dates].sort()

  return sorted.map((date) => {
    const row: Record<string, string | number | null> = { date: date.slice(5) }
    for (const [sym, pts] of Object.entries(series)) {
      const pt = pts.find((p) => p.date === date)
      row[sym] = pt?.close ?? null
    }
    return row
  })
}
