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
              <div className="metric-label">bullish probability</div>
            </div>
          </div>
          <div className="hero-details">
            <div className="detail-pill">
              <span className="label">Price</span>
              <span className="value">{fmtUsd(data.gold.price)}</span>
            </div>
            <div className={`detail-pill signal ${signalClass(data.gold.signal)}`}>
              <span className="label">Signal</span>
              <span className="value">{data.gold.signal}</span>
            </div>
            {data.gold.expected_alpha_pct != null && (
              <div className="detail-pill">
                <span className="label">Expected α</span>
                <span className="value positive-text">{data.gold.expected_alpha_pct.toFixed(2)}%</span>
              </div>
            )}
          </div>
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
            <MacroCell label="Fed Policy" value={String(data.macro.fed_probability)} small />
            <MacroCell label="Inflation" value={String(data.macro.inflation)} small />
          </div>
        </div>
      </div>

      <div className="card commodities-card">
        <div className="card-title">Markets at a Glance</div>
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
                  {Number(trend) >= 0 ? '▲' : '▼'} {Math.abs(Number(trend)).toFixed(1)}% 20d
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
