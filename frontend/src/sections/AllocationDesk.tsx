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
import { Tooltip } from '../components/Tooltip'
import type { AllocationData } from '../types'
import { METRIC_HELP } from '../utils'

const STANCE_LABEL = { add: 'Add gold', keep: 'Keep gold', reduce: 'Reduce gold' }

const PRICE_LABELS: Record<string, string> = {
  'GC=F': 'Gold',
  SPX: 'S&P 500',
  'CL=F': 'Oil',
  'HG=F': 'Copper',
}

const PRICE_COLORS: Record<string, string> = {
  'GC=F': '#d4a843',
  SPX: '#60a5fa',
  'CL=F': '#f87171',
  'HG=F': '#34d399',
}

function pct(n: number | null | undefined, digits = 1) {
  if (n == null || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(digits)}%`
}

interface AllocationDeskProps {
  allocation: AllocationData
  compact?: boolean
}

export function AllocationStance({ allocation, compact }: AllocationDeskProps) {
  return (
    <div className={`card stance-card stance-${allocation.stance}`}>
      <div className="card-header">
        <div className="card-title">Gold versus the rest of the book</div>
        <Tooltip label={METRIC_HELP.stance}>
          <span className={`stance-badge stance-${allocation.stance}`}>{STANCE_LABEL[allocation.stance]}</span>
        </Tooltip>
      </div>
      <p className="stance-summary">{allocation.summary}</p>
      {!compact && (
        <ul className="stance-reasons">
          {allocation.reasons.map((line) => <li key={line}>{line}</li>)}
        </ul>
      )}
      {compact && (
        <p className="stance-hint">Open Gold vs Markets for the comparison with stocks, oil, copper, yields, and the dollar.</p>
      )}
    </div>
  )
}

export function AllocationDesk({ allocation }: { allocation: AllocationData }) {
  const chart = allocation.relative_prices.map((row) => ({
    ...row,
    date: String(row.date).slice(5),
  }))

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Gold vs Markets</h2>
          <p className="workspace-sub">
            Should the gold budget stay, grow, or shrink versus stocks and cash? Separate from miner-versus-gold rankings.
          </p>
        </div>
      </div>

      <section className="method-note" aria-label="How this stance is produced">
        <h3>How this stance is produced</h3>
        <ol>
          <li>Gold’s number is the stored 10-day GLD model’s expected price change, not a new forecast and not a probability that gold rises.</li>
          <li>Stocks, oil, and copper each get a small gradient-boosting model fit on the same feature store, predicting that market’s next 10-day price change. The spread is gold’s number minus theirs.</li>
          <li>Real yield and the dollar’s 20-day change come from the macro snapshot. Above 2% real yield, or a dollar up more than 1% over 20 days, counts as a headwind. The regime’s gold bias is a fixed label, not a return forecast.</li>
          <li>Add requires gold ahead of stocks, no yield headwind, no dollar headwind, and a supportive regime or a falling dollar. Reduce requires gold behind stocks and at least one headwind. Anything else stays at Keep. This does not change the miner rankings.</li>
        </ol>
      </section>

      <AllocationStance allocation={allocation} />

      <div className="kpi-row" style={{ marginTop: '1.25rem' }}>
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.gold10d}><span className="kpi-label">Gold, next {allocation.horizon_days} days</span></Tooltip>
          <span className="kpi-value">{pct(allocation.gold_expected_return)}</span>
        </div>
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.real_yields}>
            <span className="kpi-label">
              Real yield
              {allocation.real_yield_source === 'estimated' ? (
                <span className="source-badge estimate">estimated</span>
              ) : allocation.real_yield_source ? (
                <span className="source-badge live">{allocation.real_yield_source}</span>
              ) : null}
            </span>
          </Tooltip>
          <span className="kpi-value">{allocation.real_yield == null ? '—' : `${allocation.real_yield.toFixed(2)}%`}</span>
          <span className={`role-tag role-${allocation.yield_role}`}>{allocation.yield_role}</span>
        </div>
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.dollar20d}><span className="kpi-label">Dollar, 20-day change</span></Tooltip>
          <span className="kpi-value">{allocation.dollar_trend_20d_pct == null ? '—' : `${allocation.dollar_trend_20d_pct.toFixed(1)}%`}</span>
          <span className={`role-tag role-${allocation.dollar_role}`}>{allocation.dollar_role}</span>
        </div>
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.environment}><span className="kpi-label">Environment</span></Tooltip>
          <span className="kpi-value" style={{ fontSize: '0.95rem' }}>{allocation.regime_name ?? '—'}</span>
          <span className="role-tag">gold {allocation.gold_bias}</span>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.25rem' }}>
        <div className="card-title">
          <Tooltip label={METRIC_HELP.spread}><span>Who is expected to do better over {allocation.horizon_days} days</span></Tooltip>
        </div>
        <p className="explain-intro">
          Each spread is gold’s expected price change minus that market’s expected price change. Positive means gold is ahead.
        </p>
        <div className="compare-list">
          {allocation.comparisons.map((row) => {
            const spreadPct = row.spread == null ? 0 : row.spread * 100
            const width = Math.min(Math.abs(spreadPct) * 8, 100)
            return (
              <div key={row.id} className="compare-row">
                <div className="compare-name">{row.label}</div>
                <div className="compare-nums">
                  <span>Gold {pct(row.gold_expected_return)}</span>
                  <span>{row.label} {pct(row.expected_return)}</span>
                </div>
                <div className="compare-bar-wrap">
                  <div
                    className={`compare-bar ${row.gold_ahead ? 'ahead' : 'behind'}`}
                    style={{ width: `${width}%` }}
                  />
                </div>
                <div className={`compare-spread ${row.gold_ahead ? 'positive-text' : 'negative-text'}`}>
                  {row.spread == null ? '—' : `${spreadPct >= 0 ? '+' : ''}${spreadPct.toFixed(1)} pp`}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="card chart-card">
        <div className="card-title">Recent leadership, rebased to 100</div>
        <p className="explain-intro">What already happened. This is not the forecast above.</p>
        {chart.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
              <ReferenceLine y={100} stroke="#64748b" strokeDasharray="4 4" />
              <RechartsTooltip contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {Object.keys(PRICE_LABELS).map((sym) => (
                <Line
                  key={sym}
                  type="monotone"
                  dataKey={sym}
                  name={PRICE_LABELS[sym]}
                  stroke={PRICE_COLORS[sym]}
                  strokeWidth={sym === 'GC=F' ? 2 : 1.5}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state"><p>No price history yet.</p></div>
        )}
      </div>

      <p className="history-footnote">{allocation.note}</p>
    </div>
  )
}
