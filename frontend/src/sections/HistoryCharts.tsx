import { useMemo, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { HistoryData } from '../types'
import { SERIES_COLORS, SERIES_LABELS } from '../utils'

const ENTITY_COLORS: Record<string, string> = {
  GLD: '#d4a843',
  GDX: '#34d399',
  GDXJ: '#60a5fa',
  RING: '#a78bfa',
  NEM: '#f87171',
  AEM: '#fbbf24',
  B: '#38bdf8',
  KGC: '#c084fc',
  AGI: '#4ade80',
}

const LOOKBACKS = [60, 90, 180, 252]
const HORIZONS = [5, 10, 20]

interface HistoryChartsProps {
  history: HistoryData
  onReload: (days: number, horizon: number) => void
  loading?: boolean
}

export function HistoryCharts({ history, onReload, loading }: HistoryChartsProps) {
  const [days, setDays] = useState(history.lookback_days)
  const [horizon, setHorizon] = useState(history.horizon_days)
  const [selectedEntities, setSelectedEntities] = useState<string[]>(['GLD', 'GDX', 'GDXJ'])

  const goldChart = useMemo(
    () =>
      history.gold_outlook.map((p) => ({
        date: p.date.slice(5),
        fullDate: p.date,
        bullish_pct: p.bullish_pct,
        alpha: p.expected_alpha != null ? Math.round(p.expected_alpha * 1000) / 10 : null,
      })),
    [history.gold_outlook],
  )

  const multiEntityChart = useMemo(() => {
    const dates = new Set<string>()
    for (const ent of selectedEntities) {
      history.entity_outlook[ent]?.series.forEach((p) => dates.add(p.date))
    }
    return [...dates].sort().map((date) => {
      const row: Record<string, string | number | null> = { date: date.slice(5), fullDate: date }
      for (const ent of selectedEntities) {
        const pt = history.entity_outlook[ent]?.series.find((p) => p.date === date)
        row[ent] = pt?.bullish_pct ?? null
      }
      return row
    })
  }, [history.entity_outlook, selectedEntities])

  const regimeChart = useMemo(
    () =>
      history.regime_history.map((r) => ({
        date: r.date.slice(5),
        fullDate: r.date,
        confidence: Math.round(r.confidence * 100),
        regime: r.regime_name,
      })),
    [history.regime_history],
  )

  const macroChart = useMemo(() => {
    const series = history.macro_series
    const dates = new Set<string>()
    Object.values(series).forEach((pts) => pts.forEach((p) => dates.add(p.date)))
    return [...dates].sort().map((date) => {
      const row: Record<string, string | number | null> = { date: date.slice(5), fullDate: date }
      for (const [sym, pts] of Object.entries(series)) {
        const pt = pts.find((p) => p.date === date)
        row[sym] = pt?.close ?? null
      }
      return row
    })
  }, [history.macro_series])

  const toggleEntity = (entity: string) => {
    setSelectedEntities((prev) => {
      if (prev.includes(entity)) {
        if (prev.length === 1) return prev
        return prev.filter((e) => e !== entity)
      }
      return [...prev, entity]
    })
  }

  const applyFilters = () => onReload(days, horizon)
  const stats = history.gold_stats

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Historical Outlook</h2>
          <p className="workspace-sub">
            How gold outlook probability, miner signals, and macro drivers evolve over time
          </p>
        </div>
        <div className="workspace-actions history-filters">
          <div className="horizon-tabs" role="group" aria-label="Lookback">
            {LOOKBACKS.map((d) => (
              <button
                key={d}
                type="button"
                className={`horizon-tab ${days === d ? 'active' : ''}`}
                onClick={() => setDays(d)}
              >
                {d}d
              </button>
            ))}
          </div>
          <div className="horizon-tabs" role="group" aria-label="Horizon">
            {HORIZONS.map((h) => (
              <button
                key={h}
                type="button"
                className={`horizon-tab ${horizon === h ? 'active' : ''}`}
                onClick={() => setHorizon(h)}
              >
                {h}d fwd
              </button>
            ))}
          </div>
          <button type="button" className="btn btn-sm" onClick={applyFilters} disabled={loading}>
            {loading ? 'Loading…' : 'Apply'}
          </button>
        </div>
      </div>

      {stats && (
        <div className="kpi-row">
          <div className="kpi-card">
            <span className="kpi-label">Latest gold bullish</span>
            <span className="kpi-value gold-text">{stats.latest}%</span>
          </div>
          <div className="kpi-card">
            <span className="kpi-label">Period avg</span>
            <span className="kpi-value">{stats.avg}%</span>
          </div>
          <div className="kpi-card">
            <span className="kpi-label">Range</span>
            <span className="kpi-value">{stats.min}% – {stats.max}%</span>
          </div>
          <div className="kpi-card">
            <span className="kpi-label">Change over period</span>
            <span className={`kpi-value ${stats.change >= 0 ? 'highlight' : 'negative-text'}`}>
              {stats.change >= 0 ? '+' : ''}{stats.change}pp
            </span>
          </div>
          <div className="kpi-card">
            <span className="kpi-label">Data points</span>
            <span className="kpi-value">{stats.n_points}</span>
          </div>
        </div>
      )}

      <div className="card chart-card" style={{ marginBottom: '1.25rem' }}>
        <div className="card-title">Gold Outlook Probability ({history.horizon_days}d horizon)</div>
        <p className="chart-caption" style={{ marginTop: 0, border: 'none', paddingTop: 0, marginBottom: '0.75rem' }}>
          Model probability that GLD outperforms gold futures over the next {history.horizon_days} trading days.
          50% = neutral baseline.
        </p>
        {goldChart.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={goldChart} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: '#64748b', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
                width={45}
              />
              <ReferenceLine y={50} stroke="#64748b" strokeDasharray="4 4" label={{ value: 'Neutral', fill: '#64748b', fontSize: 10 }} />
              <RechartsTooltip
                contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8, fontSize: 12 }}
                labelFormatter={(label) => String(label)}
                formatter={(v: number, name: string) => [
                  `${v}%`,
                  name === 'bullish_pct' ? 'Bullish %' : name,
                ]}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line
                type="monotone"
                dataKey="bullish_pct"
                name="Gold bullish %"
                stroke="#d4a843"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state">
            <p>No historical gold outlook yet.</p>
            <p className="empty-hint">Run the pipeline to backfill prediction history.</p>
          </div>
        )}
      </div>

      <div className="card chart-card" style={{ marginBottom: '1.25rem' }}>
        <div className="card-header" style={{ marginBottom: '0.75rem' }}>
          <div className="card-title" style={{ marginBottom: 0 }}>Signal Probability by Entity</div>
          <div className="filter-pills">
            {history.available_entities.map((ent) => (
              <button
                key={ent}
                type="button"
                className={`pill ${selectedEntities.includes(ent) ? 'active' : ''}`}
                onClick={() => toggleEntity(ent)}
              >
                {ent}
              </button>
            ))}
          </div>
        </div>
        {multiEntityChart.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={multiEntityChart} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} width={45} />
              <ReferenceLine y={50} stroke="#64748b" strokeDasharray="4 4" />
              <RechartsTooltip
                contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8, fontSize: 12 }}
                formatter={(v: number) => [`${v}%`, 'P(outperform)']}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {selectedEntities.map((ent) => (
                <Line
                  key={ent}
                  type="monotone"
                  dataKey={ent}
                  name={history.entity_outlook[ent]?.label ?? ent}
                  stroke={ENTITY_COLORS[ent] ?? '#94a3b8'}
                  strokeWidth={ent === 'GLD' ? 2 : 1.5}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state"><p>Select at least one entity.</p></div>
        )}
      </div>

      <div className="grid grid-2">
        <div className="card chart-card">
          <div className="card-title">Regime Confidence History</div>
          {regimeChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={regimeChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} />
                <RechartsTooltip
                  contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8, fontSize: 12 }}
                  formatter={(v: number) => [`${v}%`, 'Confidence']}
                />
                <Line type="monotone" dataKey="confidence" name="Confidence" stroke="#60a5fa" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No regime history.</p></div>
          )}
        </div>

        <div className="card chart-card">
          <div className="card-title">Macro Drivers (prices)</div>
          {macroChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={macroChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                <YAxis yAxisId="left" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} width={50} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} width={35} />
                <RechartsTooltip contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line yAxisId="left" type="monotone" dataKey="GC=F" name={SERIES_LABELS['GC=F']} stroke={SERIES_COLORS['GC=F']} strokeWidth={1.5} dot={false} connectNulls />
                <Line yAxisId="left" type="monotone" dataKey="GDX" name={SERIES_LABELS.GDX} stroke={SERIES_COLORS.GDX} strokeWidth={1.5} dot={false} connectNulls />
                <Line yAxisId="right" type="monotone" dataKey="VIX" name={SERIES_LABELS.VIX} stroke={SERIES_COLORS.VIX} strokeWidth={1} strokeDasharray="4 2" dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No macro series.</p></div>
          )}
        </div>
      </div>

      <p className="history-footnote">
        Outlook history is reconstructed by scoring the current trained models on past feature dates
        (every ~5 trading days). As you run the daily pipeline, live prediction points continue to accumulate.
      </p>
    </div>
  )
}
