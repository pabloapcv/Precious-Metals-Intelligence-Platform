export interface DashboardData {
  as_of: string
  macro: Record<string, string | number | null>
  commodities: Record<string, number | null>
  gold: {
    bullish_pct: number
    target_horizon_days: number
    signal: string
    expected_alpha_pct?: number
    price?: number | null
  }
  regime: {
    regime_name: string
    confidence: number
    description?: string
    gold_bias?: string
    miner_bias?: string
    key_drivers?: string[]
  } | null
  mining_companies: MiningCompany[]
  risk: Record<string, string | number | null>
  portfolio: PortfolioItem[]
  agent_scores: Record<string, Record<string, number>>
  etf_flows: Record<string, string | number | null>
  central_banks: {
    recent_purchases_tonnes: number
    top_buyers: Array<{ country: string; tonnes: number }>
    signal: string
  }
  insights: string[]
  data_status: {
    macro_rows: number
    predictions: number
    has_regime: boolean
    has_portfolio: boolean
    pipeline_needed: boolean
  }
}

export interface MiningCompany {
  rank: number
  entity: string
  label: string
  tier: string
  prob_outperform_gold: number
  expected_alpha: number
  horizon_days: number
}

export interface PortfolioItem {
  rank: number
  ticker: string
  weight: number
  expected_alpha: number
}

export interface SignalRow {
  entity: string
  label: string
  tier: string
  horizon_days: number
  prob_outperform_gold: number
  prob_beat_gdx: number
  expected_return: number
  expected_alpha: number
  model_version: string
  scoring_path?: string
  date: string
  signal: string
}

export interface ModelRecord {
  entity: string
  label: string
  tier: string
  horizon_days: number
  backend: string
  n_features: number
  trained_at: string | null
  walk_forward: {
    folds: number
    mean_auc: number | null
    mean_accuracy: number | null
    status: string
  }
  latest_prediction_date: string | null
  latest_prob: number | null
  scoring_path?: string
}

export interface PortfolioAnalytics {
  as_of: string
  method: string
  positions: Array<PortfolioItem & { method?: string; tier?: string }>
  analytics: {
    n_positions: number
    hhi: number
    effective_n: number
    top3_concentration: number
    max_weight_ticker: string | null
    max_weight: number
    expected_alpha_10d: number
    annualized_vol: number | null
    implied_sharpe: number | null
    tier_exposure: Record<string, number>
  }
}

export interface ResearchData {
  regime_history: Array<{
    date: string
    regime_id: number
    regime_name: string
    confidence: number
  }>
  macro_series: Record<string, Array<{ date: string; close: number | null }>>
  signal_book: Record<string, SignalRow[]>
  model_catalog: ModelRecord[]
  model_summary: {
    n_models: number
    mean_auc: number | null
    horizons: number[]
    horizon_labels?: Record<string, string>
    horizon_descriptions?: Record<string, string>
    backends: string[]
  }
  portfolio_analytics: PortfolioAnalytics
  hypotheses: Array<{
    target: string
    source: string
    direction: string
    hypothesis: string
    lag_days: number
    evidence_strength: string
  }>
  regime_definitions: Array<{
    id: number
    name: string
    gold_bias: string
    miner_bias: string
    key_drivers: string[]
  }>
  purged_evidence?: {
    generated_at: string
    horizon_days: number
    cost_bps: number
    note: string
    inference_summary?: {
      n_comparisons: number
      bootstrap_replications: number
      confidence_level: number
      seed: number
    } | null
    studies: Array<{
      name: string
      question: string
      entity: string
      benchmark: string
      horizon_days: number
      embargo_days: number
      n_oos: number
      claim: string
      auc: number | null
      accuracy: number | null
      books: Array<{
        name: string
        final_wealth: number | null
        total_return: number | null
        total_return_ci?: {
          estimate: number
          ci_lower: number
          ci_upper: number
          confidence: number
        } | null
        max_drawdown: number | null
        hit_rate: number | null
        hit_rate_ci?: {
          estimate: number
          ci_lower: number
          ci_upper: number
          confidence: number
        } | null
      }>
      dm_comparisons?: Array<{
        baseline: string
        p_value: number | null
        p_adjusted: number | null
        significant: boolean
        mean_loss_diff: number | null
        interpretation: string | null
      }>
      dm_summary?: string | null
    }>
    claims: Array<Record<string, string>>
  } | null
  integrity?: {
    history_scoring: string
    paper_scoring: string
    live_scoring: string
    cite: string
  }
}

export type WorkspaceId = 'command' | 'signals' | 'models' | 'portfolio' | 'research' | 'risk' | 'explain' | 'history' | 'allocation' | 'universe' | 'paper' | 'strategies'

export interface StrategySleeveItem {
  entity: string
  label: string
  weight: number
  signal?: string
  prob_outperform_gold?: number | null
  expected_alpha?: number | null
}

export interface StrategyPlaybook {
  id: string
  title: string
  tag: 'constructive' | 'neutral' | 'defensive' | string
  action: string
  confidence: number
  horizon_days: number
  horizon_label: string
  gold_budget: number
  sleeve: StrategySleeveItem[]
  residual: { symbol: string; weight: number; label: string }
  evidence: string[]
  caveats: string[]
  score: number
}

export interface StrategyData {
  as_of: string | null
  primary: string | null
  note: string
  drivers: {
    stance: string
    gold_budget: number
    regime_name: string | null
    gold_bias: string
    sleeve_horizon_days: number
    n_long_signals: number
    best_paper_horizon: number | null
    best_paper_return: number | null
    yield_role: string | null
    dollar_role: string | null
  }
  strategies: StrategyPlaybook[]
}

export interface PaperAccount {
  horizon_days: number
  horizon_label?: string
  starting_cash: number
  cost_bps: number
  inception: string
  as_of: string
  nav: number
  total_return: number
  max_drawdown: number
  benchmark_gold: number
  benchmark_gold_return: number
  benchmark_spx: number
  benchmark_spx_return: number
  stance: string
  gold_budget: number
  cash: number
  n_rebalances: number
  positions: Array<{ symbol: string; shares: number; price: number | null; value: number | null; weight: number | null }>
  orders: Array<{ date: string; symbol: string; side: string; shares: number; price: number; dollars: number; fee: number }>
  curve: Array<{ date: string; nav: number; gold: number; spx: number }>
}

export interface PaperData {
  starting_cash: number
  cost_bps: number
  gold_budget: { add: number; keep: number; reduce: number }
  note: string
  horizons?: number[]
  horizon_labels?: Record<string, string>
  accounts: PaperAccount[]
}

export interface PipelineStatus {
  status: 'idle' | 'running' | 'complete' | 'failed'
  started_at: string | null
  finished_at: string | null
  message: string
  error: string | null
  percent: number
  elapsed_seconds?: number | null
  stages: Array<{
    id: string
    label: string
    status: 'pending' | 'running' | 'done' | 'error'
    detail: string
    done?: number
    total?: number
  }>
  current?: {
    stage: string | null
    action: string | null
    item: string | null
    done: number
    total: number
    unit: string | null
  }
  train: { done: number; total: number; entity: string | null; horizon: number | null }
  log?: Array<{ at: string; stage: string; text: string }>
  config?: {
    preset?: string | null
    stages?: string[]
    horizons?: number[]
    train_scope?: string
    walk_forward?: boolean
    n_models?: number
  } | null
}

export interface UniverseRow {
  symbol: string
  name: string
  metal: string
  instrument: string
  tier: string
  scored: boolean
  modeled: boolean
  price: number | null
  as_of: string | null
  change_20d: number | null
  note: string
}

export interface UniverseGap {
  symbol: string
  name: string
  metal: string
  instrument: string
  note: string
}

export interface UniverseData {
  priced: UniverseRow[]
  unpriced: UniverseGap[]
  summary: {
    listed: number
    on_feed: number
    with_price: number
    awaiting_price: number
    modeled: number
    scored_next_run: number
    not_on_feed: number
    by_metal: Record<string, number>
    by_instrument: Record<string, number>
  }
}

export interface AllocationComparison {
  id: string
  label: string
  symbol: string
  expected_return: number | null
  gold_expected_return: number | null
  spread: number | null
  gold_ahead: boolean
  method: string
}

export interface AllocationData {
  as_of: string
  horizon_days: number
  stance: 'add' | 'keep' | 'reduce'
  summary: string
  reasons: string[]
  gold_expected_return: number | null
  gold_method: string
  gold_model_version?: string | null
  scoring_path?: string | null
  real_yield: number | null
  real_yield_source: string | null
  yield_role: 'headwind' | 'support' | 'neutral'
  dollar_trend_20d_pct: number | null
  dollar_role: 'headwind' | 'support' | 'neutral'
  regime_name: string | null
  gold_bias: string
  comparisons: AllocationComparison[]
  relative_prices: Array<Record<string, string | number | null>>
  note: string
}
export type SortKey = 'rank' | 'alpha' | 'prob' | 'entity' | 'signal'
export type TierFilter = 'all' | 'senior' | 'mid' | 'junior' | 'royalty' | 'gold' | 'silver' | 'pgm' | 'copper' | 'base' | 'uranium' | 'leveraged'

export interface ExplainData {
  as_of: string
  pipeline: Array<{
    id: string
    title: string
    plain: string
    technical: string
    outputs: string[]
    live: { status: string; metrics: Record<string, string | number | null> }
  }>
  signal_rules: Array<{ signal: string; condition: string; meaning: string }>
  feature_families: Array<{ name: string; examples: string[]; why: string }>
  sample_features: string[]
  data_sources: Array<{ name: string; source: string; frequency: string }>
  causal_chain: Array<{
    source: string
    target: string
    direction: string
    hypothesis: string
    magnitude_hint: string
    evidence_strength: string
  }>
  knowledge_graph_size: { nodes: number; edges: number }
  agents: Array<{
    name: string
    summary: string
    signals: string[]
    scores: Record<string, number>
    confidence: number
    timestamp: string
  }>
  signal_walkthrough: {
    entity: string
    label: string
    horizon_days: number
    signal: string
    steps: Array<{ step: string; detail: string }>
  } | null
  regime_explanation: { current: Record<string, unknown> | null; how_it_works: string }
  gold_outlook_explanation: { bullish_pct: number; plain: string }
  macro_inputs: Record<string, string | number | null>
  transparency_note: string
  claims?: Array<{ output: string; method: string; allowed_meaning: string }>
}

export interface HistoryPoint {
  date: string
  prob_outperform_gold: number | null
  prob_beat_gdx: number | null
  expected_alpha: number | null
  expected_return: number | null
  bullish_pct: number
}

export interface HistoryData {
  as_of: string
  horizon_days: number
  horizon_label?: string
  available_horizons?: number[]
  horizon_labels?: Record<string, string>
  lookback_days: number
  backfilled_rows: number
  scoring?: string
  scoring_note?: string
  gold_outlook: HistoryPoint[]
  gold_stats: {
    latest: number
    min: number
    max: number
    avg: number
    change: number
    n_points: number
  } | null
  entity_outlook: Record<string, {
    label: string
    tier: string
    series: HistoryPoint[]
  }>
  regime_history: Array<{
    date: string
    regime_id: number
    regime_name: string
    confidence: number
  }>
  macro_series: Record<string, Array<{ date: string; close: number | null }>>
  available_entities: string[]
}
