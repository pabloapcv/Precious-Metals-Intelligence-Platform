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
}

export type WorkspaceId = 'command' | 'signals' | 'models' | 'portfolio' | 'research' | 'risk' | 'explain' | 'history'
export type SortKey = 'rank' | 'alpha' | 'prob' | 'entity' | 'signal'
export type TierFilter = 'all' | 'senior' | 'mid' | 'junior' | 'royalty' | 'gold'

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
  lookback_days: number
  backfilled_rows: number
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
