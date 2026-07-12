import { Fragment, useMemo, useState } from 'react'
import type { ResearchData, SortKey, TierFilter } from '../types'
import { METRIC_HELP, exportCsv, fmtPct, signalClass } from '../utils'
import { Tooltip } from '../components/Tooltip'

interface SignalBookProps {
  research: ResearchData
}

export function SignalBook({ research }: SignalBookProps) {
  const horizons = research.model_summary.horizons.length
    ? research.model_summary.horizons
    : [10]
  const [horizon, setHorizon] = useState(horizons.includes(10) ? 10 : horizons[0])
  const [query, setQuery] = useState('')
  const [tier, setTier] = useState<TierFilter>('all')
  const [sortKey, setSortKey] = useState<SortKey>('alpha')
  const [sortAsc, setSortAsc] = useState(false)

  const signals = research.signal_book[String(horizon)] ?? []

  const filtered = useMemo(() => {
    let rows = [...signals]
    if (tier !== 'all') rows = rows.filter((s) => s.tier === tier)
    if (query.trim()) {
      const q = query.toLowerCase()
      rows = rows.filter((s) => s.entity.toLowerCase().includes(q) || s.label.toLowerCase().includes(q))
    }
    rows.sort((a, b) => {
      let cmp = 0
      if (sortKey === 'entity') cmp = a.entity.localeCompare(b.entity)
      else if (sortKey === 'alpha') cmp = a.expected_alpha - b.expected_alpha
      else if (sortKey === 'prob') cmp = a.prob_outperform_gold - b.prob_outperform_gold
      else if (sortKey === 'signal') cmp = a.signal.localeCompare(b.signal)
      return sortAsc ? cmp : -cmp
    })
    return rows
  }, [signals, tier, query, sortKey, sortAsc])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v)
    else { setSortKey(key); setSortAsc(key === 'entity') }
  }

  const sortInd = (key: SortKey) => (sortKey === key ? (sortAsc ? ' ↑' : ' ↓') : '')

  const handleExport = () => {
    exportCsv(
      `pmip_signals_h${horizon}_${new Date().toISOString().slice(0, 10)}.csv`,
      filtered.map((s) => ({
        entity: s.entity,
        label: s.label,
        tier: s.tier,
        signal: s.signal,
        prob_outperform_gold: s.prob_outperform_gold,
        prob_beat_gdx: s.prob_beat_gdx,
        expected_alpha: s.expected_alpha,
        expected_return: s.expected_return,
        horizon_days: s.horizon_days,
        model_version: s.model_version,
        date: s.date,
      })),
    )
  }

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Signal Book</h2>
          <p className="workspace-sub">Tradeable alpha signals · multi-horizon ML outputs · exportable</p>
        </div>
        <div className="workspace-actions">
          <div className="horizon-tabs" role="tablist">
            {horizons.map((h) => (
              <button
                key={h}
                type="button"
                role="tab"
                aria-selected={horizon === h}
                className={`horizon-tab ${horizon === h ? 'active' : ''}`}
                onClick={() => setHorizon(h)}
              >
                {h}d
              </button>
            ))}
          </div>
          <button type="button" className="btn btn-ghost" onClick={handleExport} disabled={!filtered.length}>
            Export CSV
          </button>
        </div>
      </div>

      <div className="toolbar">
        <input
          type="search"
          className="search-input"
          placeholder="Filter ticker…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="filter-pills">
          {(['all', 'gold', 'senior', 'mid', 'junior', 'royalty'] as TierFilter[]).map((t) => (
            <button
              key={t}
              type="button"
              className={`pill ${tier === t ? 'active' : ''}`}
              onClick={() => setTier(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="card table-card">
        <div className="table-wrap">
          <table className="data-table institutional">
            <thead>
              <tr>
                <th><button type="button" className="th-btn" onClick={() => toggleSort('entity')}>Ticker{sortInd('entity')}</button></th>
                <th>Name</th>
                <th>Tier</th>
                <th><button type="button" className="th-btn" onClick={() => toggleSort('signal')}>Signal{sortInd('signal')}</button></th>
                <th className="num"><button type="button" className="th-btn" onClick={() => toggleSort('prob')}>P(Gold){sortInd('prob')}</button></th>
                <th className="num">P(GDX)</th>
                <th className="num"><Tooltip label={METRIC_HELP.alpha}><span>Exp α{sortInd('alpha')}</span></Tooltip></th>
                <th className="num">Exp Ret</th>
                <th>Model</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={9} className="empty-row">No signals for this horizon — run pipeline.</td></tr>
              ) : (
                filtered.map((s) => (
                  <tr key={`${s.entity}-${s.horizon_days}`}>
                    <td className="mono gold-text">{s.entity}</td>
                    <td>{s.label}</td>
                    <td><span className="tier-badge">{s.tier}</span></td>
                    <td><span className={`signal-badge ${signalClass(s.signal)}`}>{s.signal}</span></td>
                    <td className="num mono">{fmtPct(s.prob_outperform_gold, 0)}</td>
                    <td className="num mono">{fmtPct(s.prob_beat_gdx, 0)}</td>
                    <td className={`num mono ${s.expected_alpha >= 0 ? 'positive-text' : 'negative-text'}`}>
                      {fmtPct(s.expected_alpha)}
                    </td>
                    <td className="num mono">{fmtPct(s.expected_return)}</td>
                    <td className="model-ver">{s.model_version}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="table-footer">{filtered.length} signals · horizon {horizon}d</div>
      </div>
    </div>
  )
}
