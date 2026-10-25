import { ColumnGuide } from '../components/ColumnGuide'
import { Tooltip } from '../components/Tooltip'
import type { DashboardData } from '../types'
import { METRIC_HELP, biasClass, fmt, fmtUsd, signalClass } from '../utils'

interface OverviewSectionProps {
  data: DashboardData
}

export function OverviewSection({ data }: OverviewSectionProps) {
  const bullish = data.gold.bullish_pct
  const gaugeRotation = (bullish / 100) * 180 - 90

  return (
    <div className="overview-panel">
      {data.insights.length > 0 && (
        <div className="insights-strip">
          {data.insights.map((line, i) => (
            <div key={i} className="insight-chip">
              <span className="insight-dot" aria-hidden />
              {line}
            </div>
          ))}
        </div>
      )}

      <section className="method-note" aria-label="How the figures on this page are produced">
        <h3>How the figures on this page are produced</h3>
        <ol>
          <li>Prices on the markets strip are the latest Yahoo Finance closes stored for gold, silver, oil, copper, the S&amp;P 500, and the GDX miners ETF. A “20-day change” is the latest close divided by the close 20 trading days earlier, minus one.</li>
          <li>The gold dial is the 10-day GLD model only. It is the chance GLD’s next 10-day return beats gold futures, scored on the newest feature row. It is not the chance the gold price rises, and it does not change when you open the 5-day or 20-day signal book.</li>
          <li>Real yield is the 10-year Treasury yield minus expected inflation when FRED data is present, otherwise the 10-year yield minus 2.25. The regime name comes from a four-state statistical fit. Its gold bias is a fixed label for that state.</li>
        </ol>
      </section>

      <div className="hero-grid">
        <div className="card hero-card">
          <div className="card-header">
            <div className="card-title">Gold Outlook</div>
            <Tooltip label={METRIC_HELP.prob}>
              <span className="help-label">10-day forecast</span>
            </Tooltip>
          </div>
          <div className="hero-gauge-wrap">
            <div className="gauge" aria-hidden>
              <div className="gauge-track" />
              <div
                className="gauge-needle"
                style={{ transform: `rotate(${gaugeRotation}deg)` }}
              />
            </div>
            <div className="hero-metric">
              <div className={`metric-value xl ${bullish >= 55 ? 'gold' : bullish < 45 ? 'negative-text' : ''}`}>
                {bullish}%
              </div>
              <div className="metric-label">P(Gold), next 10 days</div>
            </div>
          </div>
          <div className="hero-details">
            <div className="detail-pill">
              <span className="label">Price</span>
              <span className="value">{fmtUsd(data.gold.price)}</span>
            </div>
            <div className={`detail-pill signal ${signalClass(data.gold.signal)}`}>
              <Tooltip label={METRIC_HELP.signal}><span className="label">Signal</span></Tooltip>
              <span className="value">{data.gold.signal}</span>
            </div>
            {data.gold.expected_alpha_pct != null && (
              <div className="detail-pill">
                <Tooltip label={METRIC_HELP.alpha}><span className="label">Expected alpha</span></Tooltip>
                <span className="value positive-text">{data.gold.expected_alpha_pct.toFixed(2)}%</span>
              </div>
            )}
          </div>
          <ColumnGuide items={[
            { term: 'P(Gold)', text: METRIC_HELP.prob },
            { term: 'Signal', text: METRIC_HELP.signal },
            { term: 'Expected alpha', text: METRIC_HELP.alpha },
          ]} />
          <div className="bullish-bar" role="progressbar" aria-valuenow={bullish} aria-valuemin={0} aria-valuemax={100}>
            <div className="bullish-fill" style={{ width: `${bullish}%` }} />
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Market Regime</div>
            <Tooltip label={METRIC_HELP.regime}>
              <span className="help-label">HMM classification</span>
            </Tooltip>
          </div>
          {data.regime ? (
            <>
              <div className="regime-badge">{data.regime.regime_name}</div>
              <div className="confidence-row">
                <span>Confidence</span>
                <div className="mini-bar">
                  <div
                    className="mini-bar-fill"
                    style={{ width: `${(data.regime.confidence * 100).toFixed(0)}%` }}
                  />
                </div>
                <span className="mono">{(data.regime.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="bias-row">
                <span className={`bias-chip ${biasClass(data.regime.gold_bias)}`}>
                  Gold {data.regime.gold_bias}
                </span>
                <span className={`bias-chip ${biasClass(data.regime.miner_bias)}`}>
                  Miners {data.regime.miner_bias}
                </span>
              </div>
              {data.regime.description && (
                <p className="regime-desc">{data.regime.description}</p>
              )}
              {data.regime.key_drivers && (
                <div className="tags">
                  {data.regime.key_drivers.map((d) => <span key={d} className="tag">{d}</span>)}
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              <p>No regime detected yet.</p>
              <p className="empty-hint">Run the pipeline to classify the current macro environment.</p>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-title">Macro Snapshot</div>
          <div className="macro-grid">
            <MacroCell
              label="Real Yields"
              value={data.macro.real_yields != null ? `${Number(data.macro.real_yields).toFixed(2)}%` : '—'}
              sub={String(data.macro.real_yield_source || '')}
              help={METRIC_HELP.real_yields}
            />
            <MacroCell
              label="10Y Nominal"
              value={data.macro.nominal_10y != null ? `${Number(data.macro.nominal_10y).toFixed(2)}%` : '—'}
              help={METRIC_HELP.nominal10y}
            />
            <MacroCell
              label="DXY"
              value={fmt(data.macro.dxy as number)}
              sub={data.macro.dxy_trend_20d_pct != null ? `${data.macro.dxy_trend_20d_pct}% 20d` : ''}
              help={METRIC_HELP.dxy}
              trend={Number(data.macro.dxy_trend_20d_pct) > 0 ? 'up' : Number(data.macro.dxy_trend_20d_pct) < 0 ? 'down' : undefined}
            />
            <MacroCell
              label="VIX"
              value={fmt(data.macro.vix as number, 1)}
              help={METRIC_HELP.vix}
            />
            <MacroCell label="Fed Policy" value={String(data.macro.fed_probability)} help={METRIC_HELP.fed} small />
            <MacroCell label="Inflation" value={String(data.macro.inflation)} help={METRIC_HELP.inflation} small />
          </div>
        </div>
      </div>

      <div className="card commodities-card">
        <div className="card-title">
          <Tooltip label={METRIC_HELP.change20d}><span>Markets at a Glance</span></Tooltip>
        </div>
        <div className="commodity-row">
          {[
            ['Gold', data.commodities.gold, data.macro.gold_trend_20d_pct as number | null],
            ['Silver', data.commodities.silver, null],
            ['Oil (WTI)', data.commodities.oil, null],
            ['Copper', data.commodities.copper, null],
            ['S&P 500', data.commodities.spx, null],
            ['GDX Miners', data.commodities.gdx, null],
          ].map(([label, val, trend]) => (
            <div key={String(label)} className="commodity-item">
              <div className="label">{label}</div>
              <div className="value">{fmtUsd(val as number | null)}</div>
              {trend != null && (
                <div className={`trend ${Number(trend) >= 0 ? 'positive-text' : 'negative-text'}`}>
                  {Number(trend) >= 0 ? '▲' : '▼'} {Math.abs(Number(trend)).toFixed(1)}% 20-day change
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function MacroCell({
  label,
  value,
  sub,
  help,
  small,
  trend,
}: {
  label: string
  value: string
  sub?: string
  help?: string
  small?: boolean
  trend?: 'up' | 'down'
}) {
  return (
    <div className="macro-item">
      <div className="macro-item-head">
        {help ? (
          <Tooltip label={help}><span className="label">{label}</span></Tooltip>
        ) : (
          <span className="label">{label}</span>
        )}
        {trend && <span className={`trend-icon ${trend}`} aria-hidden>{trend === 'up' ? '▲' : '▼'}</span>}
      </div>
      <div className={`value ${small ? 'small' : ''}`}>{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  )
}
