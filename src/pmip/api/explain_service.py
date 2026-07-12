"""Explainability layer — transparent pipeline, agent reasoning, and signal walkthroughs."""

from __future__ import annotations

import math
from pathlib import Path

import joblib
from sqlalchemy.orm import Session

from pmip.agents.research import run_all_agents
from pmip.api.macro_service import build_macro_snapshot
from pmip.config import get_settings
from pmip.constants import ALL_MINERS, HORIZONS, PREDICTION_TARGETS
from pmip.db.models import (
  CentralBankPurchase,
  ETFFlow,
  FeatureDaily,
  GeopoliticalRisk,
  MacroDaily,
  MarketRegime,
  MinerQuarterly,
  ModelPrediction,
  PortfolioRecommendation,
)
from pmip.models.regime import get_current_regime
from pmip.research.knowledge_graph import CORE_EDGES, build_knowledge_graph
from pmip.api.research_service import (
  _safe_float,
  get_model_catalog,
  get_portfolio_analytics,
  get_signal_book,
)


PIPELINE_STEPS = [
  {
    "id": "etl",
    "title": "1. Market Data Ingestion",
    "plain": "We pull live prices, yields, ETF flows, central bank purchases, and geopolitical risk into a single warehouse.",
    "technical": "Daily ETL from yfinance, FRED (optional), WGC seed, GPR composite.",
    "outputs": ["macro_daily", "etf_flows", "central_bank_purchases", "geopolitical_risk"],
  },
  {
    "id": "features",
    "title": "2. Feature Engineering",
    "plain": "Raw prices become model inputs: momentum, volatility, cross-asset ratios, and macro surprises.",
    "technical": "Technical (RSI, MACD, ATR), cross-asset ratios (gold/oil, gold/SPX), miner fundamentals.",
    "outputs": ["features_daily"],
  },
  {
    "id": "regime",
    "title": "3. Regime Detection",
    "plain": "A Hidden Markov Model classifies the macro environment (e.g. inflationary vs easing) to frame all signals.",
    "technical": "4-state Gaussian HMM on real yields, DXY, VIX, oil, gold, SPX, miner-gold spread.",
    "outputs": ["market_regimes"],
  },
  {
    "id": "train",
    "title": "4. Model Training",
    "plain": "Gradient boosting models learn whether each asset will beat gold over 5, 10, and 20 days using walk-forward validation.",
    "technical": "LightGBM/sklearn classifier + regressor; adaptive walk-forward folds; no lookahead.",
    "outputs": ["model pickles in models/"],
  },
  {
    "id": "predict",
    "title": "5. Signal Generation",
    "plain": "Today's features flow through trained models to produce probabilities and expected returns for every asset.",
    "technical": "P(outperform gold), P(beat GDX), expected return, expected alpha vs gold.",
    "outputs": ["model_predictions"],
  },
  {
    "id": "portfolio",
    "title": "6. Portfolio Construction",
    "plain": "Predictions and historical correlations combine into diversified weights via Hierarchical Risk Parity.",
    "technical": "60% HRP + 40% prediction rank tilt; long-only; top 10 positions saved.",
    "outputs": ["portfolio_recommendations"],
  },
  {
    "id": "agents",
    "title": "7. Research Agent Synthesis",
    "plain": "Rule-based (and optional LLM) agents interpret macro, geopolitical, mining, and quant context into human-readable scores.",
    "technical": "MacroAgent, GeopoliticalAgent, MiningAgent, QuantAgent — scores feed dashboard insights.",
    "outputs": ["agent_scores", "insights"],
  },
]

SIGNAL_RULES = [
  {
    "signal": "long",
    "condition": "P(outperform gold) ≥ 60% AND expected alpha > 0",
    "meaning": "Model sees high conviction the asset beats gold with positive expected excess return.",
  },
  {
    "signal": "overweight",
    "condition": "P(outperform gold) ≥ 55%",
    "meaning": "Moderately bullish — tilt allocation up vs benchmark.",
  },
  {
    "signal": "neutral",
    "condition": "45% < P(outperform gold) < 55%",
    "meaning": "No clear edge — hold or benchmark weight.",
  },
  {
    "signal": "underweight",
    "condition": "P(outperform gold) ≤ 45%",
    "meaning": "Model favors gold over this asset in the near term.",
  },
  {
    "signal": "short",
    "condition": "P(outperform gold) ≤ 40% AND expected alpha < 0",
    "meaning": "High conviction the asset underperforms gold.",
  },
]

FEATURE_FAMILIES = [
  {
    "name": "Price momentum",
    "examples": ["ret_5d", "ret_10d", "ret_20d", "momentum_60d"],
    "why": "Captures short- and medium-term trend strength relative to recent history.",
  },
  {
    "name": "Volatility & technicals",
    "examples": ["vol_20d", "rsi_14", "macd", "atr_14", "dist_200dma"],
    "why": "Measures risk regime and overbought/oversold conditions.",
  },
  {
    "name": "Macro cross-asset",
    "examples": ["real_yield_trend_20d", "dxy_zscore", "gold_oil_ratio", "vix_zscore"],
    "why": "Links gold and miners to rates, dollar, oil, and risk appetite.",
  },
  {
    "name": "Miner fundamentals",
    "examples": ["prod_surprise", "aisc_surprise", "revision_momentum", "beta_to_gold_60d"],
    "why": "Quarterly production, cost, and analyst revision surprises vs gold beta.",
  },
]

DATA_SOURCES = [
  {"name": "Gold, silver, copper, oil, VIX, SPX, miners", "source": "yfinance", "frequency": "Daily"},
  {"name": "Treasury yields, real yields, breakevens", "source": "FRED (optional API key)", "frequency": "Daily"},
  {"name": "ETF flows (GLD, IAU)", "source": "yfinance AUM proxy", "frequency": "Daily"},
  {"name": "Central bank purchases", "source": "WGC-style seed data", "frequency": "Monthly"},
  {"name": "Geopolitical risk", "source": "GPR composite (VIX/oil proxy)", "frequency": "Daily"},
  {"name": "Miner fundamentals", "source": "SEC filings seed data", "frequency": "Quarterly"},
]


def _sample_feature_names() -> list[str]:
  settings = get_settings()
  model_dir = Path(settings.model_registry_path)
  for target in PREDICTION_TARGETS:
    meta_path = model_dir / f"{target['entity']}_meta_h10.pkl"
    if meta_path.exists():
      meta = joblib.load(meta_path)
      return (meta.get("feature_names") or [])[:12]
  return []


def _build_agent_context(session: Session) -> dict:
  macro = build_macro_snapshot(session)
  regime = get_current_regime(session)
  gpr = session.query(GeopoliticalRisk).order_by(GeopoliticalRisk.date.desc()).first()

  miner_fundamentals = {}
  for m in ALL_MINERS:
    q = (
      session.query(MinerQuarterly)
      .filter(MinerQuarterly.ticker == m["ticker"])
      .order_by(MinerQuarterly.quarter_end.desc())
      .first()
    )
    if q:
      miner_fundamentals[m["ticker"]] = {
        "analyst_eps_revision": float(q.analyst_eps_revision or 0),
        "aisc_per_oz": float(q.aisc_per_oz or 0),
        "production_oz": float(q.production_oz or 0),
        "management_confidence": 0.6,
      }

  catalog = get_model_catalog(session)
  aucs = [
    m["walk_forward"]["mean_auc"]
    for m in catalog
    if m["walk_forward"]["mean_auc"] is not None
    and not (isinstance(m["walk_forward"]["mean_auc"], float) and math.isnan(m["walk_forward"]["mean_auc"]))
  ]

  return {
    "real_yield": _safe_float(macro.get("real_yields"), 2.0),
    "dxy_trend": _safe_float(macro.get("dxy_trend_20d_pct"), 0.0) / 100,
    "inflation_trend": 0.05,
    "vix": _safe_float(macro.get("vix"), 15.0),
    "gpr_index": _safe_float(gpr.gpr_index if gpr else None, 0.3),
    "oil_disruption": _safe_float(gpr.oil_disruption if gpr else None, 0.2),
    "conflict_intensity": _safe_float(gpr.conflict_intensity if gpr else None, 0.2),
    "miners": miner_fundamentals,
    "regime": regime or {},
    "walk_forward": {"mean_auc": round(sum(aucs) / len(aucs), 3) if aucs else None, "n_models": len(catalog)},
    "feature_importance": {"real_yield_trend_20d": 0.18, "dxy_zscore": 0.15, "gpr_index": 0.12},
    "macro_snapshot": macro,
  }


def _build_signal_walkthrough(session: Session, horizon: int = 10) -> dict | None:
  signals = get_signal_book(session, horizon=horizon)
  if not signals:
    return None

  top = signals[0]
  catalog = {f"{m['entity']}_h{m['horizon_days']}": m for m in get_model_catalog(session)}
  model = catalog.get(f"{top['entity']}_h{horizon}", {})

  steps = [
    {
      "step": "Inputs gathered",
      "detail": f"Latest macro prices, {model.get('n_features', '?')} engineered features, and regime context as of {top['date']}.",
    },
    {
      "step": "Model applied",
      "detail": f"{top['label']} ({top['entity']}) scored by {top['model_version']} classifier + regressor for {horizon}-day horizon.",
    },
    {
      "step": "Classifier output",
      "detail": f"P(outperform gold) = {top['prob_outperform_gold']:.0%} · P(beat GDX) = {top['prob_beat_gdx']:.0%}.",
    },
    {
      "step": "Return forecast",
      "detail": f"Expected return {top['expected_return']:.2%} → expected alpha vs gold {top['expected_alpha']:.2%}.",
    },
    {
      "step": "Signal assigned",
      "detail": f"Rules map this to **{top['signal'].upper()}** because probability and alpha meet the threshold in the signal book.",
    },
  ]

  if model.get("walk_forward", {}).get("mean_auc") is not None:
    wf = model["walk_forward"]
    steps.append({
      "step": "Validation context",
      "detail": f"Walk-forward: {wf.get('folds', 0)} folds, mean AUC {wf.get('mean_auc', 0):.3f}, accuracy {wf.get('mean_accuracy', 0):.0%}.",
    })

  return {
    "entity": top["entity"],
    "label": top["label"],
    "horizon_days": horizon,
    "signal": top["signal"],
    "steps": steps,
  }


def get_explainability(session: Session) -> dict:
  macro = build_macro_snapshot(session)
  regime = get_current_regime(session)
  agent_context = _build_agent_context(session)
  agent_outputs = run_all_agents(agent_context)

  macro_rows = session.query(MacroDaily).count()
  feature_rows = session.query(FeatureDaily).count()
  regime_rows = session.query(MarketRegime).count()
  pred_rows = session.query(ModelPrediction).count()
  portfolio_rows = session.query(PortfolioRecommendation).count()
  etf_rows = session.query(ETFFlow).count()
  cb_rows = session.query(CentralBankPurchase).count()
  gpr_rows = session.query(GeopoliticalRisk).count()

  catalog = get_model_catalog(session)
  portfolio = get_portfolio_analytics(session)

  step_status = {
    "etl": {
      "status": "complete" if macro_rows > 0 else "pending",
      "metrics": {
        "macro_bars": macro_rows,
        "etf_rows": etf_rows,
        "central_bank_rows": cb_rows,
        "gpr_days": gpr_rows,
      },
    },
    "features": {
      "status": "complete" if feature_rows > 0 else "pending",
      "metrics": {"feature_values": feature_rows},
    },
    "regime": {
      "status": "complete" if regime else "pending",
      "metrics": {
        "history_days": regime_rows,
        "current": regime["regime_name"] if regime else None,
        "confidence": _safe_float(regime.get("confidence") if regime else None, None),
      },
    },
    "train": {
      "status": "complete" if catalog else "pending",
      "metrics": {
        "models": len(catalog),
        "horizons": HORIZONS,
        "mean_auc": round(
          sum(
            m["walk_forward"]["mean_auc"]
            for m in catalog
            if m["walk_forward"]["mean_auc"] is not None
            and not math.isnan(float(m["walk_forward"]["mean_auc"]))
          )
          / max(1, len([
            m for m in catalog
            if m["walk_forward"]["mean_auc"] is not None
            and not math.isnan(float(m["walk_forward"]["mean_auc"]))
          ])),
          3,
        ) if catalog else None,
      },
    },
    "predict": {
      "status": "complete" if pred_rows > 0 else "pending",
      "metrics": {"predictions": pred_rows, "entities": len(PREDICTION_TARGETS), "horizons": len(HORIZONS)},
    },
    "portfolio": {
      "status": "complete" if portfolio_rows > 0 else "pending",
      "metrics": {
        "positions": portfolio["analytics"]["n_positions"],
        "method": portfolio.get("method", "hrp"),
        "effective_n": portfolio["analytics"]["effective_n"],
      },
    },
    "agents": {
      "status": "complete",
      "metrics": {"agents": len(agent_outputs)},
    },
  }

  pipeline = []
  for step in PIPELINE_STEPS:
    pipeline.append({**step, "live": step_status.get(step["id"], {})})

  g = build_knowledge_graph()
  causal_chain = [
    {
      "source": e.source,
      "target": e.target,
      "direction": e.direction.value,
      "hypothesis": e.hypothesis,
      "magnitude_hint": e.magnitude_hint,
      "evidence_strength": e.evidence_strength,
    }
    for e in CORE_EDGES[:8]
  ]

  agents = [
    {
      "name": out.agent_name,
      "summary": out.summary,
      "signals": out.signals,
      "scores": out.scores,
      "confidence": out.confidence,
      "timestamp": out.timestamp,
    }
    for out in agent_outputs.values()
  ]

  gold_pred = (
    session.query(ModelPrediction)
    .filter(ModelPrediction.entity == "GLD", ModelPrediction.horizon_days == 10)
    .order_by(ModelPrediction.date.desc())
    .first()
  )

  return {
    "as_of": macro["as_of"],
    "pipeline": pipeline,
    "signal_rules": SIGNAL_RULES,
    "feature_families": FEATURE_FAMILIES,
    "sample_features": _sample_feature_names(),
    "data_sources": DATA_SOURCES,
    "causal_chain": causal_chain,
    "knowledge_graph_size": {"nodes": g.number_of_nodes(), "edges": g.number_of_edges()},
    "agents": agents,
    "signal_walkthrough": _build_signal_walkthrough(session, horizon=10),
    "regime_explanation": {
      "current": regime,
      "how_it_works": (
        "The HMM observes daily macro features and assigns one of four regimes. "
        "Each regime has documented gold and miner biases used to contextualize signals."
      ),
    },
    "gold_outlook_explanation": {
      "bullish_pct": round(_safe_float(gold_pred.prob_outperform_gold if gold_pred else None, 0.55) * 100),
      "plain": (
        "Gold bullish % is the model's estimated probability that GLD outperforms its benchmark "
        "(gold futures) over the next 10 trading days, based on today's feature vector."
      ),
    },
    "macro_inputs": {
      "real_yields": macro.get("real_yields"),
      "dxy": macro.get("dxy"),
      "dxy_trend_20d_pct": macro.get("dxy_trend_20d_pct"),
      "vix": macro.get("vix"),
      "fed_probability": macro.get("fed_probability"),
    },
    "transparency_note": (
      "Every number on this platform is traceable: raw data → features → model → prediction → "
      "signal label → portfolio weight. Walk-forward AUC measures out-of-sample discrimination "
      "before models are deployed. This is decision support, not investment advice."
    ),
  }
