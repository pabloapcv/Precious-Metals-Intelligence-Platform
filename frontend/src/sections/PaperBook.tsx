import { useState } from 'react'
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
import { Tooltip } from '../components/Tooltip'
import type { PaperData } from '../types'
import { METRIC_HELP, horizonLabel } from '../utils'

function money(n: number) {
  return n.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

function pct(n: number) {
  return `${n >= 0 ? '+' : ''}${(n * 100).toFixed(1)}%`
}

export function PaperBook({ paper, onOpenPipeline }: { paper: PaperData; onOpenPipeline?: () => void }) {
  const labels = paper.horizon_labels
  const [horizon, setHorizon] = useState(paper.accounts.find((a) => a.horizon_days === 10)?.horizon_days ?? paper.accounts[0]?.horizon_days)
  const account = paper.accounts.find((item) => item.horizon_days === horizon) ?? paper.accounts[0]
  if (!account) {
    return (
      <div className="workspace">
        <div className="empty-state">
          <p>Paper books have not been marked yet.</p>
          <p className="empty-hint">Run the history / paper stages so as-of scores can mark the books.</p>
          {onOpenPipeline ? (
            <button type="button" className="btn btn-sm" onClick={onOpenPipeline} style={{ marginTop: '0.75rem' }}>
              Run pipeline
            </button>
          ) : null}
        </div>
      </div>
    )
  }

  const accountLabel = account.horizon_label || horizonLabel(account.horizon_days, labels)
  const chart = account.curve.map((row) => ({ ...row, date: row.date.slice(5) }))

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Paper Books</h2>
          <p className="workspace-sub">
            Separate {money(paper.starting_cash)} accounts for 5d, 10d, 1m, 3m, and 6m. Each trades only its own forecasts.
          </p>
        </div>
        <div className="horizon-tabs" role="tablist">
          {paper.accounts.map((item) => (
            <button
              key={item.horizon_days}
              type="button"
              className={`horizon-tab ${item.horizon_days === account.horizon_days ? 'active' : ''}`}
              onClick={() => setHorizon(item.horizon_days)}
            >
              {item.horizon_label || horizonLabel(item.horizon_days, labels)}
            </button>
          ))}
        </div>
      </div>

      <section className="method-note">
        <h3>How the {accountLabel} book is traded</h3>
        <p className="explain-intro">{paper.note}</p>
        <p className="explain-intro">
          <span className="source-badge asof">as-of</span> scores only.
          Last stance is not the same object as Gold vs Markets (trailing SPX here vs 10-day SPX model there).
        </p>
      </section>

      <div className="kpi-row">
        {paper.accounts.map((item) => (
          <button
            key={item.horizon_days}
            type="button"
            className={`kpi-card ${item.horizon_days === account.horizon_days ? 'active' : ''}`}
            onClick={() => setHorizon(item.horizon_days)}
          >
            <span className="kpi-label">{item.horizon_label || horizonLabel(item.horizon_days, labels)} book</span>
            <span className="kpi-value">{money(item.nav)}</span>
            <span className={`role-tag ${item.total_return >= 0 ? 'role-support' : 'role-headwind'}`}>{pct(item.total_return)}</span>
          </button>
        ))}
      </div>

      <div className="kpi-row">
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.paperNav}><span className="kpi-label">This book</span></Tooltip>
          <span className="kpi-value">{money(account.nav)}</span>
          <Tooltip label={METRIC_HELP.paperReturn}><span className="role-tag">{pct(account.total_return)} since {account.inception}</span></Tooltip>
        </div>
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.paperGoldBench}><span className="kpi-label">Hold gold</span></Tooltip>
          <span className="kpi-value">{money(account.benchmark_gold)}</span>
          <span className="role-tag">{pct(account.benchmark_gold_return)}</span>
        </div>
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.paperSpxBench}><span className="kpi-label">Hold S&P 500</span></Tooltip>
          <span className="kpi-value">{money(account.benchmark_spx)}</span>
          <span className="role-tag">{pct(account.benchmark_spx_return)}</span>
        </div>
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.paperStance}><span className="kpi-label">Last stance</span></Tooltip>
          <span className="kpi-value" style={{ fontSize: '1rem' }}>{account.stance}</span>
          <span className="role-tag">{Math.round(account.gold_budget * 100)}% gold sleeve · {account.n_rebalances} rebalances</span>
        </div>
      </div>

      <div className="card chart-card">
        <div className="card-title">{accountLabel} account versus holding gold and holding the S&P 500</div>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chart}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={64} />
            <RechartsTooltip contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="nav" name={`${accountLabel} book`} stroke="#d4a843" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="gold" name="Hold gold" stroke="#34d399" strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="spx" name="Hold S&P 500" stroke="#60a5fa" strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-2" style={{ marginTop: '1.25rem' }}>
        <div className="card table-card">
          <div className="card-title">Positions</div>
          <div className="table-wrap">
            <table className="data-table institutional">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th className="num">Shares</th>
                  <th className="num">Value</th>
                  <th className="num">Weight</th>
                </tr>
              </thead>
              <tbody>
                {account.positions.map((row) => (
                  <tr key={row.symbol}>
                    <td className="mono gold-text">{row.symbol}</td>
                    <td className="num mono">{row.shares.toLocaleString()}</td>
                    <td className="num mono">{row.value == null ? '—' : money(row.value)}</td>
                    <td className="num mono">{row.weight == null ? '—' : `${(row.weight * 100).toFixed(1)}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card table-card">
          <div className="card-title">Latest trades</div>
          <div className="table-wrap">
            <table className="data-table institutional">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Side</th>
                  <th>Symbol</th>
                  <th className="num">Dollars</th>
                </tr>
              </thead>
              <tbody>
                {account.orders.map((row, index) => (
                  <tr key={`${row.date}-${row.symbol}-${row.side}-${index}`}>
                    <td className="mono">{row.date.slice(5)}</td>
                    <td>{row.side}</td>
                    <td className="mono">{row.symbol}</td>
                    <td className="num mono">{money(row.dollars)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
