import { Fragment, useMemo, useState } from 'react'
import type { ResearchData, SortKey, TierFilter } from '../types'
import { ColumnGuide } from '../components/ColumnGuide'
import { Tooltip } from '../components/Tooltip'
import { METRIC_HELP, exportCsv, fmtPct, horizonLabel, signalClass } from '../utils'

interface SignalBookProps {
  research: ResearchData
  onOpenPipeline?: () => void
}

function pathLabel(path?: string) {
  if (path === 'asof_embargo') return 'as-of'
  return 'live'
}

export function SignalBook({ research, onOpenPipeline }: SignalBookProps) {
  const horizons = research.model_summary.horizons.length
    ? research.model_summary.horizons
    : [5, 10, 20, 63, 126]
  const labels = research.model_summary.horizon_labels
  const [horizon, setHorizon] = useState(horizons.includes(10) ? 10 : horizons[0])
  const hLabel = horizonLabel(horizon, labels)
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
        scoring_path: s.scoring_path ?? 'full_sample_live',
        date: s.date,
      })),
    )
  }

  return (
    <div className="workspace">
      <div className="workspace-head">
        <div>
          <h2 className="workspace-title">Signal Book · {hLabel}</h2>
          <p className="workspace-sub">
            Each row is that name’s latest <span className="source-badge live">live</span> full-sample
            forecast for the next {horizon} trading days ({hLabel}).
            {signals[0]?.date ? ` As of ${signals[0].date}.` : ''}
            {' '}Paper books and history use purged as-of scores instead.
          </p>
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
                {horizonLabel(h, labels)}
              </button>
            ))}
          </div>
          <button type="button" className="btn btn-ghost" onClick={handleExport} disabled={!filtered.length}>
            Export CSV
          </button>
        </div>
      </div>

      <section className="method-note" aria-label="How these forecasts are produced">
        <h3>How this {hLabel} table is produced</h3>
        <ol>
          <li>
            Daily closing prices are downloaded from Yahoo Finance for each future, ETF, and stock, and stored in the warehouse.
            Treasury yields come from FRED when a key is set. Without one, the real yield is the 10-year yield minus 2.25 percentage points.
          </li>
          <li>
            Those closes are turned into the model’s inputs: trailing returns, volatility, gold versus the S&amp;P 500, gold versus copper, the real yield, and the dollar’s change over 20 trading days.
          </li>
          <li>
            The {hLabel} tab loads a separate saved model for each name, tagged <span className="mono">{signals[0]?.model_version ?? `h${horizon}`}</span>.
            It was trained to answer one question: did this name’s return over the next {horizon} trading days beat gold futures (GC=F)?
            A second model on the same inputs estimates the price change itself.
          </li>
          <li>
            Each row is that pair of models scored once, on the newest feature day{signals[0]?.date ? ` (${signals[0].date})` : ''}.
            Switching tabs (5d / 10d / 1m / 3m / 6m) swaps in the other saved model. Older scores are not averaged into this table.
          </li>
          <li>
            P(Gold) is the classifier’s probability. Expected return is the second model’s price change.
            Expected alpha subtracts a flat 1% from that price change. P(GDX)* multiplies P(Gold) by 0.95. The signal word is a cutoff on the probability and the alpha, not a third model.
          </li>
          <li>
            Scoring path is <span className="mono">full_sample_live</span> on this page.
            Cite Model Validation and Paper Books for purged evidence — do not treat these live rows as a track record.
          </li>
        </ol>
      </section>

      <div className="toolbar">
        <input
          type="search"
          className="search-input"
          placeholder="Filter ticker…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="filter-pills">
          {(['all', 'gold', 'silver', 'pgm', 'copper', 'base', 'uranium', 'senior', 'mid', 'junior', 'royalty', 'leveraged'] as TierFilter[]).map((t) => (
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

      <ColumnGuide items={[
        { term: 'P(Gold)', text: METRIC_HELP.prob },
        { term: 'P(GDX)*', text: METRIC_HELP.probGdx },
        { term: 'Expected alpha', text: METRIC_HELP.alpha },
        { term: 'Expected return', text: METRIC_HELP.expectedReturn },
        { term: 'Signal', text: METRIC_HELP.signal },
        { term: 'Model', text: METRIC_HELP.model },
        { term: 'Path', text: METRIC_HELP.scoringPath },
      ]} />

      <div className="card table-card">
        <div className="table-wrap">
          <table className="data-table institutional">
            <thead>
              <tr>
                <th><Tooltip label={METRIC_HELP.ticker}><button type="button" className="th-btn" onClick={() => toggleSort('entity')}>Ticker{sortInd('entity')}</button></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.name}><span>Name</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.tier}><span>Tier</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.signal}><button type="button" className="th-btn" onClick={() => toggleSort('signal')}>Signal{sortInd('signal')}</button></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.prob}><button type="button" className="th-btn" onClick={() => toggleSort('prob')}>P(Gold){sortInd('prob')}</button></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.probGdx}><span>P(GDX)*</span></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.alpha}><button type="button" className="th-btn" onClick={() => toggleSort('alpha')}>Expected alpha{sortInd('alpha')}</button></Tooltip></th>
                <th className="num"><Tooltip label={METRIC_HELP.expectedReturn}><span>Expected return</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.scoringPath}><span>Path</span></Tooltip></th>
                <th><Tooltip label={METRIC_HELP.model}><span>Model</span></Tooltip></th>
              </tr>
            </thead>
            <tbody key={horizon}>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="empty-row">
                    No {horizon}-day forecasts yet.{' '}
                    {onOpenPipeline ? (
                      <button type="button" className="btn btn-sm" onClick={onOpenPipeline}>Run pipeline</button>
                    ) : (
                      'Run the pipeline.'
                    )}
                  </td>
                </tr>
              ) : (
                filtered.map((s) => (
                  <tr key={`${s.entity}-${s.horizon_days}-${s.date}`}>
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
                    <td>
                      <Tooltip label={METRIC_HELP.scoringPath}>
                        <span className={`source-badge ${s.scoring_path === 'asof_embargo' ? 'asof' : 'live'}`}>
                          {pathLabel(s.scoring_path)}
                        </span>
                      </Tooltip>
                    </td>
                    <td className="model-ver">{s.model_version}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="table-footer">
          {filtered.length} names · next {horizon} trading days
          {signals[0]?.date ? ` · forecast date ${signals[0].date}` : ''}
          {' · '}full-sample live · P(GDX)* is 95% of P(Gold). Expected alpha subtracts a flat 1% hurdle.
        </div>
      </div>
    </div>
  )
}
