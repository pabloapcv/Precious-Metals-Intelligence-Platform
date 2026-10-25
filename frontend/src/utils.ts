export function fmt(n: number | null | undefined, digits = 2) {
  if (n == null || Number.isNaN(n)) return '—'
  return n.toLocaleString(undefined, { maximumFractionDigits: digits })
}

export function fmtUsd(n: number | null | undefined) {
  if (n == null) return '—'
  return `$${fmt(n, n > 100 ? 0 : 2)}`
}

export function fmtPct(n: number, digits = 1) {
  return `${(n * 100).toFixed(digits)}%`
}

/** Short label for forecast horizons (trading days → desk shorthand). */
export function horizonLabel(days: number, labels?: Record<string, string> | null) {
  if (labels?.[String(days)]) return labels[String(days)]
  const defaults: Record<number, string> = { 5: '5d', 10: '10d', 20: '1m', 63: '3m', 126: '6m' }
  return defaults[days] ?? `${days}d`
}

export function signalClass(signal: string) {
  if (['bullish', 'rising', 'long', 'overweight'].includes(signal)) return 'positive'
  if (['bearish', 'declining', 'short', 'underweight'].includes(signal)) return 'negative'
  return 'neutral'
}

export function biasClass(bias: string | undefined) {
  if (bias === 'bullish') return 'positive'
  if (bias === 'bearish') return 'negative'
  return 'neutral'
}

export function exportCsv(filename: string, rows: Record<string, unknown>[]) {
  if (rows.length === 0) return
  const headers = Object.keys(rows[0])
  const lines = [
    headers.join(','),
    ...rows.map((row) =>
      headers.map((h) => {
        const v = row[h]
        const s = v == null ? '' : String(v)
        return s.includes(',') ? `"${s}"` : s
      }).join(','),
    ),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const METRIC_HELP: Record<string, string> = {
  alpha: 'The model’s expected price change minus a flat 1% hurdle. Use it to rank names. It is not a measured excess return versus gold.',
  prob: 'The chance the model gives that this name’s return beats gold futures over the horizon you selected. For GLD, that is a tracking gap versus the futures contract, not the chance the gold price rises.',
  probGdx: 'This is 95% of P(Gold). No separate model estimates the chance of beating the GDX miners ETF.',
  expectedReturn: 'The model’s expected price change over the selected horizon, before the 1% hurdle is subtracted.',
  signal: 'A label from the probability and the expected alpha: long, overweight, neutral, underweight, or short.',
  tier: 'The sleeve this name belongs to, such as gold, silver, senior miner, royalty, or copper.',
  model: 'Which saved model wrote the row, including the horizon. “sklearn” means the histogram gradient-boosting fallback.',
  ticker: 'The exchange or feed symbol used to pull the price.',
  name: 'The plain-language name of the instrument.',
  auc: 'Walk-forward AUC. How well the model separated names that beat gold from names that did not, on past windows it was not trained on. 0.50 is a coin toss. 1.00 is a perfect split. The stored catalog uses the embargo only after the next pipeline run.',
  accuracy: 'On those same past test windows, the share of days where a probability above 50% matched what actually happened.',
  folds: 'How many separate past test windows were scored.',
  latestP: 'Today’s probability that this name beats gold futures over this horizon.',
  horizon: 'How far ahead the forecast looks: 5d, 10d, ~1 month (20d), ~3 months (63d), or ~6 months (126d).',
  features: 'How many inputs that model was allowed to use.',
  backend: 'The algorithm that was fit. On this machine that is scikit-learn histogram gradient boosting when LightGBM cannot load.',
  trained: 'The calendar date the model file was saved.',
  status: 'Whether that horizon finished training or was skipped for lack of data.',
  entity: 'The instrument the row refers to.',
  hhi: 'Concentration of the book. Near 1 means one name holds almost everything. Near 0 means weights are spread out.',
  effective_n: 'How many equal positions the book behaves like. It is 1 divided by HHI. A book of 8 names can still have an effective N near 5 if a few weights dominate.',
  sharpe: 'A rough return-per-risk figure: the book’s 10-day expected alpha, scaled to a year, divided by how much the book has actually moved. It is not a live track record.',
  positions: 'How many names currently receive a weight.',
  portAlpha: 'The weight-averaged expected alpha of the book over 10 days.',
  annVol: 'How widely the book’s holdings have moved together over recent history, scaled to a full year.',
  top3: 'The share of the book sitting in the three largest positions.',
  weight: 'This name’s share of the gold sleeve. Weights are long-only and scaled to 100%.',
  real_yields: 'The 10-year Treasury yield minus expected inflation. Above 2% is treated as a headwind for gold. Below 1% is treated as support. Without a FRED key this is estimated from the nominal yield.',
  nominal10y: 'The 10-year US Treasury yield, before subtracting inflation.',
  dxy: 'The US dollar index. The “20d” figure is the percent change versus 20 trading days ago, not an average.',
  vix: 'The S&P 500 volatility index. Higher means the equity market is pricing larger near-term moves.',
  fed: 'A label from the real yield: dovish if real yields are under 1%, hawkish if they are over 2%, otherwise neutral. It is not a probability of a Fed decision.',
  inflation: 'A label from 10-year breakeven inflation: cooling under 2%, elevated over 2.5%, otherwise moderate.',
  gpr: 'A geopolitical risk score stored with the daily data. The “war probability” badge says rising only when this score is above 0.5. It is a threshold, not a probability.',
  conflict: 'The conflict-intensity score stored alongside geopolitical risk. Higher means the feed is flagging more conflict.',
  oilDisruption: 'Says rising when the stored oil-disruption score is above 0.4. Otherwise stable.',
  cbBuying: 'Recent official-sector gold purchases, in tonnes. The signal says rising when the latest month is above 30 tonnes.',
  etfFlow: 'Estimated daily share change for the gold ETF, in millions. Declining means the latest GLD flow is negative.',
  hrp: 'Hierarchical risk parity. It groups holdings that move together and then spreads risk across those groups.',
  regime: 'The current environment label from a four-state statistical model. Confidence is how cleanly that model fit, not how sure the gold call is.',
  change20d: 'Percent change from the close 20 trading days ago to the latest close. That is about one calendar month. It is a start-to-end move, not the average of the daily moves in between.',
  lastPrice: 'The latest closing price on the price feed.',
  metal: 'Which metal the instrument mainly exposes you to.',
  instrument: 'How you own the exposure: future, bullion ETF, miner ETF, producer, royalty, developer, or a geared fund.',
  modelStatus: 'Live means a prediction is already stored. Next pipeline means a model will be trained on the next run. Tracked only means we store the price and do not fit a model, which is how geared funds are handled.',
  listed: 'Every instrument class on the book, including ones the price feed cannot mark.',
  priced: 'How many listed instruments have a stored close.',
  withModel: 'How many names already have a saved prediction.',
  notOnFeed: 'Instrument classes the industry trades that this daily file does not price, such as LME nickel or coin premiums.',
  gold10d: 'The gold model’s expected price change over the next 10 trading days. This is a price change, not the chance gold rises, and not excess return versus futures.',
  dollar20d: 'Percent change in the dollar index versus 20 trading days ago. Above +1% is treated as a headwind for the gold budget. Below −1% is treated as support.',
  environment: 'The current regime name, plus whether that regime’s fixed table calls gold bullish, bearish, or neutral.',
  spread: 'Gold’s expected 10-day price change minus that market’s expected 10-day price change, in percentage points. Positive means gold is ahead.',
  bullishLatest: 'The latest stored chance that GLD beats gold futures. The line is rescored with today’s model on past feature dates.',
  periodAvg: 'The average of those stored probabilities over the window you selected.',
  range: 'The lowest and highest stored probability in that window.',
  periodChange: 'Latest probability minus the first probability in the window, in percentage points.',
  points: 'How many stored dates are in the window. History is sampled about every five trading days.',
  output: 'The number or label as it appears on the screen.',
  method: 'How that number is produced.',
  allowed: 'What you can safely say the number means.',
  label: 'The signal word the screen prints.',
  rule: 'The cutoff that turns a probability and an alpha into that word.',
  interpretation: 'The action that word is meant to suggest inside a gold book.',
  data: 'The series being ingested.',
  source: 'Where the series is pulled from.',
  freq: 'How often a new observation arrives.',
  absent: 'Why this instrument has no daily close in the warehouse.',
  dataBars: 'How many daily price and macro rows are stored in the warehouse.',
  modelsCount: 'How many entity-and-horizon model files are saved and ready to score.',
  backendLive: 'Which algorithm wrote the live forecasts. On this machine that is usually scikit-learn histogram gradient boosting.',
  paperNav: 'Mark-to-market value of this paper account after costs. Starts at $100,000.',
  paperGoldBench: 'What the same $100,000 would be worth if it had only held gold from inception.',
  paperSpxBench: 'What the same $100,000 would be worth if it had only held the S&P 500 from inception.',
  paperStance: 'The last Keep, Add, or Reduce call used on a rebalance day, and the gold-sleeve weight that call mapped to.',
  paperReturn: 'Ending account value divided by the starting $100,000, minus one.',
  stance: 'Keep, Add, or Reduce for the gold budget versus stocks and cash. Add is 60% gold sleeve, Keep 30%, Reduce 10%.',
  cbTonnes: 'Recent official-sector gold purchases, in tonnes, from the stored central-bank table.',
}

export const SERIES_LABELS: Record<string, string> = {
  'GC=F': 'Gold',
  'DX-Y.NYB': 'DXY',
  GDX: 'GDX Miners',
  US10Y_REAL: 'Real 10Y',
  VIX: 'VIX',
}

export const SERIES_COLORS: Record<string, string> = {
  'GC=F': '#d4a843',
  'DX-Y.NYB': '#60a5fa',
  GDX: '#34d399',
  US10Y_REAL: '#a78bfa',
  VIX: '#f87171',
}
