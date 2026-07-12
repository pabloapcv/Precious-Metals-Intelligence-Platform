import { Fragment, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Tooltip } from '../components/Tooltip'
import type { DashboardData, SortKey, TierFilter } from '../types'
import { METRIC_HELP, fmtPct } from '../utils'

const TIERS: { id: TierFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'senior', label: 'Senior' },
  { id: 'mid', label: 'Mid' },
  { id: 'junior', label: 'Junior' },
  { id: 'royalty', label: 'Royalty' },
]

interface MiningSectionProps {
  companies: DashboardData['mining_companies']
}

export function MiningSection({ companies }: MiningSectionProps) {
  const [query, setQuery] = useState('')
  const [tier, setTier] = useState<TierFilter>('all')
  const [sortKey, setSortKey] = useState<SortKey>('rank')
  const [sortAsc, setSortAsc] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)

  const filtered = useMemo(() => {
    let rows = [...companies]
    if (tier !== 'all') rows = rows.filter((m) => m.tier === tier)
    if (query.trim()) {
      const q = query.toLowerCase()
      rows = rows.filter(
        (m) => m.label.toLowerCase().includes(q) || m.entity.toLowerCase().includes(q),
      )
    }
    rows.sort((a, b) => {
      let cmp = 0
      if (sortKey === 'rank') cmp = a.rank - b.rank
      else if (sortKey === 'alpha') cmp = a.expected_alpha - b.expected_alpha
      else cmp = a.prob_outperform_gold - b.prob_outperform_gold
      return sortAsc ? cmp : -cmp
    })
    return rows
  }, [companies, tier, query, sortKey, sortAsc])

  const chartData = filtered.slice(0, 8).map((m) => ({
    name: m.entity,
    alpha: Math.round(m.expected_alpha * 1000) / 10,
    prob: Math.round(m.prob_outperform_gold * 100),
  }))

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v)
    else {
      setSortKey(key)
      setSortAsc(key === 'rank')
    }
  }

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return ''
    return sortAsc ? ' ↑' : ' ↓'
  }

  return (
    <section id="mining" className="section">
      <div className="section-head">
        <div>
          <h2 className="section-title">Mining Picks</h2>
          <p className="section-subtitle">Ranked by expected alpha vs gold over a 10-day horizon</p>
        </div>
        <Tooltip label={METRIC_HELP.alpha}>
          <span className="help-label">How alpha is calculated</span>
        </Tooltip>
      </div>

      <div className="toolbar">
        <input
          type="search"
          className="search-input"
          placeholder="Search ticker or company…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search mining picks"
        />
        <div className="filter-pills" role="group" aria-label="Filter by tier">
          {TIERS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`pill ${tier === t.id ? 'active' : ''}`}
              onClick={() => setTier(t.id)}
              aria-pressed={tier === t.id}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {companies.length === 0 ? (
        <div className="card empty-state">
          <p>No predictions yet.</p>
          <p className="empty-hint">Run the pipeline to train models and generate mining rankings.</p>
        </div>
      ) : (
        <>
          {chartData.length > 0 && (
            <div className="card chart-card">
              <div className="card-title">Expected Alpha — Top {chartData.length}</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis
                    tick={{ fill: '#94a3b8', fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <RechartsTooltip
                    contentStyle={{ background: '#1a2234', border: '1px solid #2a3548', borderRadius: 8 }}
                    formatter={(v: number, name: string) => [
                      `${v}%`,
                      name === 'alpha' ? 'Expected α' : 'Prob vs gold',
                    ]}
                  />
                  <Bar dataKey="alpha" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, i) => (
                      <Cell
                        key={entry.name}
                        fill={entry.alpha >= 0 ? '#34d399' : '#f87171'}
                        opacity={0.85 + (chartData.length - i) * 0.015}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="card table-card">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>
                      <button type="button" className="th-btn" onClick={() => toggleSort('rank')}>
                        # {sortIndicator('rank')}
                      </button>
                    </th>
                    <th>Company</th>
                    <th>Tier</th>
                    <th className="num">
                      <button type="button" className="th-btn" onClick={() => toggleSort('alpha')}>
                        Expected α {sortIndicator('alpha')}
                      </button>
                    </th>
                    <th className="num">
                      <button type="button" className="th-btn" onClick={() => toggleSort('prob')}>
                        vs Gold {sortIndicator('prob')}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="empty-row">No matches — try a different filter or search.</td>
                    </tr>
                  ) : (
                    filtered.map((m) => {
                      const isOpen = expanded === m.entity
                      return (
                        <Fragment key={m.entity}>
                          <tr
                            className={`table-row ${isOpen ? 'expanded' : ''}`}
                            onClick={() => setExpanded(isOpen ? null : m.entity)}
                            tabIndex={0}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                setExpanded(isOpen ? null : m.entity)
                              }
                            }}
                            role="button"
                            aria-expanded={isOpen}
                          >
                            <td><span className="miner-rank">{m.rank}</span></td>
                            <td>
                              <span className="miner-name">{m.label}</span>
                              <span className="miner-ticker">{m.entity}</span>
                            </td>
                            <td><span className="tier-badge">{m.tier}</span></td>
                            <td className="num">
                              <span className={`miner-alpha ${m.expected_alpha >= 0 ? '' : 'negative-text'}`}>
                                {fmtPct(m.expected_alpha)}
                              </span>
                              <div className="inline-bar">
                                <div
                                  className="inline-bar-fill positive"
                                  style={{ width: `${Math.min(Math.abs(m.expected_alpha) * 500, 100)}%` }}
                                />
                              </div>
                            </td>
                            <td className="num">
                              <span className="mono">{fmtPct(m.prob_outperform_gold, 0)}</span>
                              <div className="inline-bar">
                                <div
                                  className="inline-bar-fill gold"
                                  style={{ width: `${m.prob_outperform_gold * 100}%` }}
                                />
                              </div>
                            </td>
                          </tr>
                          {isOpen && (
                            <tr className="detail-row">
                              <td colSpan={5}>
                                <div className="row-detail">
                                  <span><strong>{m.entity}</strong> · {m.horizon_days}-day horizon</span>
                                  <span>
                                    Model assigns {fmtPct(m.prob_outperform_gold, 0)} probability of beating gold
                                    with {fmtPct(m.expected_alpha)} expected alpha.
                                  </span>
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              Showing {filtered.length} of {companies.length} picks · Click a row for details
            </div>
          </div>
        </>
      )}
    </section>
  )
}
