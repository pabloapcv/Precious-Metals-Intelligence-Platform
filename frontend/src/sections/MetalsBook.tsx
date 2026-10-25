import { useMemo, useState } from 'react'
import { Tooltip } from '../components/Tooltip'
import type { UniverseData } from '../types'
import { METRIC_HELP } from '../utils'

const INSTRUMENT_LABEL: Record<string, string> = {
  future: 'Future',
  bullion_etf: 'Bullion ETF',
  miner_etf: 'Miner ETF',
  leveraged: 'Leveraged',
  producer: 'Producer',
  royalty: 'Royalty / stream',
  developer: 'Developer',
  otc_rate: 'OTC rate',
  physical: 'Physical',
  option: 'Option',
  private: 'Private contract',
}

function money(n: number | null) {
  if (n == null) return '—'
  if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (n >= 20) return n.toFixed(2)
  return n.toFixed(3)
}

function pct(n: number | null) {
  if (n == null || Number.isNaN(n)) return '—'
  return `${n >= 0 ? '+' : ''}${(n * 100).toFixed(1)}%`
}

export function MetalsBook({ universe }: { universe: UniverseData }) {
  const [metal, setMetal] = useState('all')
  const [instrument, setInstrument] = useState('all')
  const [query, setQuery] = useState('')

  const metals = useMemo(
    () => ['all', ...Object.keys(universe.summary.by_metal).sort()],
    [universe.summary.by_metal],
  )
  const instruments = useMemo(
    () => ['all', ...Object.keys(universe.summary.by_instrument).sort()],
    [universe.summary.by_instrument],
  )

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return universe.priced.filter((row) => {
      if (metal !== 'all' && row.metal !== metal) return false
      if (instrument !== 'all' && row.instrument !== instrument) return false
      if (!q) return true
      return row.symbol.toLowerCase().includes(q) || row.name.toLowerCase().includes(q)
    })
  }, [universe.priced, metal, instrument, query])

  const s = universe.summary

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Metals Book</h2>
          <p className="workspace-sub">
            Futures, bullion ETFs, miners, royalty companies, and geared funds across gold, silver, platinum group metals, copper, and the rest of the mined-metal complex.
          </p>
        </div>
      </div>

      <section className="method-note" aria-label="How these prices are produced">
        <h3>How these prices are produced</h3>
        <ol>
          <li>Each priced row is the latest daily close downloaded from Yahoo Finance and stored in the warehouse. Nothing on this page is a model forecast.</li>
          <li>20-day change is the latest close divided by the close 20 trading days earlier, minus one. It is that start-to-end move, not an average of the days in between.</li>
          <li>Model says Live when a forecast already exists in the signal book, Next pipeline when the next run will train one, and Tracked only for geared funds that we price but do not model. The rows at the bottom have no close because the feed does not carry them.</li>
        </ol>
      </section>

      <div className="kpi-row">
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.listed}><span className="kpi-label">Instrument classes</span></Tooltip>
          <span className="kpi-value">{s.listed}</span>
        </div>
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.priced}><span className="kpi-label">Priced on the feed</span></Tooltip>
          <span className="kpi-value">{s.with_price}</span>
          <span className="role-tag">{s.awaiting_price} still loading</span>
        </div>
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.withModel}><span className="kpi-label">With a model</span></Tooltip>
          <span className="kpi-value">{s.modeled}</span>
          <span className="role-tag">{s.scored_next_run} train on the next pipeline</span>
        </div>
        <div className="kpi-card">
          <Tooltip label={METRIC_HELP.notOnFeed}><span className="kpi-label">Not on this feed</span></Tooltip>
          <span className="kpi-value">{s.not_on_feed}</span>
        </div>
      </div>

      <div className="toolbar">
        <input
          className="search-input"
          placeholder="Search ticker or name"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="filter-pills">
          {metals.map((id) => (
            <button key={id} type="button" className={`pill ${metal === id ? 'active' : ''}`} onClick={() => setMetal(id)}>
              {id}
            </button>
          ))}
        </div>
        <div className="filter-pills">
          {instruments.map((id) => (
            <button key={id} type="button" className={`pill ${instrument === id ? 'active' : ''}`} onClick={() => setInstrument(id)}>
              {id === 'all' ? 'all types' : INSTRUMENT_LABEL[id] ?? id}
            </button>
          ))}
        </div>
      </div>

      <div className="card table-card">
        <div className="table-wrap">
          <table className="data-table institutional">
            <thead>
              <tr>
                <th><Tooltip label={METRIC_HELP.ticker}><span>Ticker</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.name}><span>Name</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.metal}><span>Metal</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.instrument}><span>Instrument</span></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.lastPrice}><span>Last</span></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.change20d}><span>20-day change</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.modelStatus}><span>Model</span></Tooltip></th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan={7} className="empty-row">Nothing matches this filter.</td></tr>
              ) : rows.map((row) => (
                <tr key={row.symbol}>
                  <td className="mono gold-text">{row.symbol}</td>
                  <td>{row.name}</td>
                  <td><span className="tier-badge">{row.metal}</span></td>
                  <td>{INSTRUMENT_LABEL[row.instrument] ?? row.instrument}</td>
                  <td className="num mono">{money(row.price)}</td>
                  <td className={`num mono ${row.change_20d != null && row.change_20d < 0 ? 'negative-text' : 'positive-text'}`}>
                    {pct(row.change_20d)}
                  </td>
                  <td>{row.modeled ? 'Live' : row.scored ? 'Next pipeline' : 'Tracked only'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="table-footer">{rows.length} instruments</div>
      </div>

      <div className="card" style={{ marginTop: '1.25rem' }}>
        <div className="card-title">Traded in the industry, not marked on this feed</div>
        <p className="explain-intro">
          These are real metals-market instruments. The daily price file used here does not carry them, so the book lists the gap instead of inventing a close.
        </p>
        <div className="table-wrap">
          <table className="data-table institutional">
            <thead>
              <tr>
                <th><Tooltip label={METRIC_HELP.name}><span>Name</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.metal}><span>Metal</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.instrument}><span>Type</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.absent}><span>Why it is absent</span></Tooltip></th>
              </tr>
            </thead>
            <tbody>
              {universe.unpriced.map((row) => (
                <tr key={row.symbol}>
                  <td>{row.name}</td>
                  <td><span className="tier-badge">{row.metal}</span></td>
                  <td>{INSTRUMENT_LABEL[row.instrument] ?? row.instrument}</td>
                  <td>{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
