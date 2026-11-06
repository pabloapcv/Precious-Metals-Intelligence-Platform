"""Institutional research desk analytics — regime history, signal book, portfolio risk."""

from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from pmip.config import get_settings
from pmip.constants import HORIZON_DESCRIPTIONS, HORIZONS, PREDICTION_TARGETS, horizon_label
from pmip.db.models import MacroDaily, MarketRegime, ModelPrediction, PortfolioRecommendation
from pmip.portfolio.optimizer import _get_return_matrix
from pmip.research.knowledge_graph import REGIME_HYPOTHESES, get_hypotheses_for_target


def _safe_float(value, default: float | None = 0.0) -> float | None:
  if value is None:
    return default
  try:
    num = float(value)
  except (TypeError, ValueError):
    return default
  if math.isnan(num) or math.isinf(num):
    return default
  return num


LABEL_MAP = {t["entity"]: t for t in PREDICTION_TARGETS}


def get_regime_history(session: Session, days: int = 120) -> list[dict]:
  cutoff = date.today() - timedelta(days=days)
  rows = (
    session.query(MarketRegime)
    .filter(MarketRegime.date >= cutoff)
    .order_by(MarketRegime.date)
    .all()
  )
  return [
    {
      "date": r.date.isoformat(),
      "regime_id": r.regime_id,
      "regime_name": r.regime_name,
      "confidence": _safe_float(r.confidence, 0.0),
    }
    for r in rows
  ]


def get_macro_series(session: Session, symbols: list[str] | None = None, days: int = 252) -> dict:
  symbols = symbols or ["GC=F", "DX-Y.NYB", "GDX", "US10Y_REAL", "VIX"]
  cutoff = date.today() - timedelta(days=days)
  rows = (
    session.query(MacroDaily)
    .filter(MacroDaily.symbol.in_(symbols), MacroDaily.date >= cutoff)
    .order_by(MacroDaily.date)
    .all()
  )
  series: dict[str, list[dict]] = {s: [] for s in symbols}
  for r in rows:
    if r.symbol in series:
      series[r.symbol].append({
        "date": r.date.isoformat(),
        "close": _safe_float(r.close, None),
      })
  return series


def get_signal_book(session: Session, horizon: int = 10) -> list[dict]:
  """One row per name: latest live (full-sample) forecast for this horizon."""
  from pmip.models.asof import is_asof_version, scoring_path_for_version

  rows = (
    session.query(ModelPrediction)
    .filter(ModelPrediction.horizon_days == horizon)
    .order_by(ModelPrediction.date.desc(), ModelPrediction.id.desc())
    .all()
  )
  latest: dict[str, ModelPrediction] = {}
  for row in rows:
    # Desk signal book never uses purged as-of history scores.
    if is_asof_version(row.model_version):
      continue
    if row.entity not in latest:
      latest[row.entity] = row
  rows = sorted(latest.values(), key=lambda row: _safe_float(row.expected_alpha, 0.0), reverse=True)
  return [
    {
      "entity": r.entity,
      "label": LABEL_MAP.get(r.entity, {}).get("label", r.entity),
      "tier": LABEL_MAP.get(r.entity, {}).get("tier", "unknown"),
      "horizon_days": r.horizon_days,
      "prob_outperform_gold": _safe_float(r.prob_outperform_gold, 0.5),
      "prob_beat_gdx": _safe_float(r.prob_beat_gdx, 0.5),
      "expected_return": _safe_float(r.expected_return, 0.0),
      "expected_alpha": _safe_float(r.expected_alpha, 0.0),
      "model_version": r.model_version or "unknown",
      "scoring_path": scoring_path_for_version(r.model_version),
      "date": r.date.isoformat(),
      "signal": _classify_signal(
        _safe_float(r.prob_outperform_gold, 0.5),
        _safe_float(r.expected_alpha, 0.0),
      ),
    }
    for r in rows
  ]


def _classify_signal(prob: float, alpha: float) -> str:
  if prob >= 0.6 and alpha > 0:
    return "long"
  if prob <= 0.4 and alpha < 0:
    return "short"
  if prob >= 0.55:
    return "overweight"
  if prob <= 0.45:
    return "underweight"
  return "neutral"


def get_model_catalog(session: Session) -> list[dict]:
  settings = get_settings()
  model_dir = Path(settings.model_registry_path)
  catalog: list[dict] = []

  for target in PREDICTION_TARGETS:
    entity = target["entity"]
    for horizon in HORIZONS:
      meta_path = model_dir / f"{entity}_meta_h{horizon}.pkl"
      if not meta_path.exists():
        continue
      meta = joblib.load(meta_path)
      wf = meta.get("walk_forward") or {}
      from pmip.models.asof import latest_live_prediction

      pred = latest_live_prediction(session, entity=entity, horizon=horizon)
      catalog.append({
        "entity": entity,
        "label": target["label"],
        "tier": target["tier"],
        "horizon_days": horizon,
        "backend": meta.get("backend", "unknown"),
        "n_features": len(meta.get("feature_names") or []),
        "trained_at": meta.get("trained_at"),
        "walk_forward": {
          "folds": wf.get("folds", 0),
          "mean_auc": _safe_float(wf.get("mean_auc"), None),
          "mean_accuracy": _safe_float(wf.get("mean_accuracy"), None),
          "status": wf.get("status", "not_run" if wf.get("skipped") else "ok"),
        },
        "latest_prediction_date": pred.date.isoformat() if pred else None,
        "latest_prob": _safe_float(pred.prob_outperform_gold, None) if pred else None,
        "scoring_path": "full_sample_live",
      })

  catalog.sort(key=lambda x: (x["entity"], x["horizon_days"]))
  return catalog


def get_portfolio_analytics(session: Session) -> dict:
  rows = (
    session.query(PortfolioRecommendation)
    .order_by(PortfolioRecommendation.date.desc(), PortfolioRecommendation.rank)
    .limit(10)
    .all()
  )
  if not rows:
    return {"positions": [], "analytics": {}}

  rec_date = rows[0].date
  positions = [
    {
      "rank": p.rank,
      "ticker": p.ticker,
      "weight": _safe_float(p.weight, 0.0),
      "expected_alpha": _safe_float(p.expected_alpha, 0.0),
      "method": p.method or "hrp",
      "tier": LABEL_MAP.get(p.ticker, {}).get("tier", "unknown"),
    }
    for p in rows
  ]

  weights = np.array([p["weight"] for p in positions])
  hhi = float(np.sum(weights ** 2))
  effective_n = float(1 / hhi) if hhi > 0 else 0.0
  top3_concentration = float(np.sum(np.sort(weights)[::-1][:3])) if len(weights) >= 3 else float(weights.sum())

  tier_exposure: dict[str, float] = {}
  for p in positions:
    tier = p["tier"]
    tier_exposure[tier] = tier_exposure.get(tier, 0.0) + p["weight"]

  expected_return = float(sum(p["weight"] * p["expected_alpha"] for p in positions))
  horizon_days = 10

  tickers = [p["ticker"] for p in positions]
  returns = _get_return_matrix(session, tickers, lookback=126)
  port_vol = None
  sharpe = None
  max_weight_ticker = positions[0]["ticker"] if positions else None

  if not returns.empty and len(returns.columns) >= 2:
    w = pd.Series({p["ticker"]: p["weight"] for p in positions}).reindex(returns.columns).fillna(0)
    w = w / w.sum() if w.sum() > 0 else w
    cov = returns.cov()
    port_var = float(w @ cov @ w)
    port_vol = float(np.sqrt(port_var) * np.sqrt(252)) if port_var > 0 else None
    if port_vol and port_vol > 0:
      ann_alpha = expected_return * (252 / horizon_days)
      sharpe = ann_alpha / port_vol

  return {
    "as_of": rec_date.isoformat(),
    "method": positions[0]["method"] if positions else "hrp",
    "positions": positions,
    "analytics": {
      "n_positions": len(positions),
      "hhi": round(hhi, 4),
      "effective_n": round(effective_n, 2),
      "top3_concentration": round(top3_concentration, 4),
      "max_weight_ticker": max_weight_ticker,
      "max_weight": round(float(weights.max()), 4) if len(weights) else 0,
      "expected_alpha_10d": round(expected_return, 4),
      "annualized_vol": round(port_vol, 4) if port_vol else None,
      "implied_sharpe": round(sharpe, 2) if sharpe else None,
      "tier_exposure": {k: round(v, 4) for k, v in tier_exposure.items()},
    },
  }


def get_research_hypotheses() -> list[dict]:
  """Key causal hypotheses for gold and miners — research desk reference."""
  targets = ["Gold", "Senior Gold Miners", "GDX", "Real Interest Rates"]
  hypotheses = []
  for target in targets:
    edges = get_hypotheses_for_target(target)
    for e in edges[:3]:
      hypotheses.append({
        "target": target,
        "source": e.source,
        "direction": e.direction.value,
        "hypothesis": e.hypothesis,
        "lag_days": e.lag_days,
        "evidence_strength": e.evidence_strength,
      })
  return hypotheses


def load_purged_evidence() -> dict | None:
  """Load the citeable purged walk-forward study from ``docs/research/results.json``."""
  from pmip.config import PROJECT_ROOT

  path = PROJECT_ROOT / "docs" / "research" / "results.json"
  if not path.exists():
    return None
  try:
    import json

    payload = json.loads(path.read_text())
  except Exception:
    return None

  studies = []
  for study in payload.get("studies") or []:
    if study.get("error"):
      continue
    metrics = study.get("metrics") or {}
    backtest = study.get("backtest") or {}
    hgb = metrics.get("gradient_boosting") or {}
    books = []
    for name, row in backtest.items():
      if not isinstance(row, dict):
        continue
      books.append({
        "name": name,
        "final_wealth": row.get("final_wealth"),
        "total_return": row.get("total_return"),
        "total_return_ci": row.get("total_return_ci"),
        "max_drawdown": row.get("max_drawdown"),
        "hit_rate": row.get("hit_rate"),
        "hit_rate_ci": row.get("hit_rate_ci"),
      })

    stat_tests = study.get("statistical_tests", {})
    dm_comparisons = []
    for comp in stat_tests.get("comparisons", []):
      dm_comparisons.append({
        "baseline": comp.get("baseline"),
        "p_value": comp.get("dm_test", {}).get("p_value"),
        "p_adjusted": comp.get("p_adjusted"),
        "significant": comp.get("significant_after_holm"),
        "mean_loss_diff": comp.get("dm_test", {}).get("mean_loss_diff"),
        "interpretation": comp.get("interpretation"),
      })

    studies.append({
      "name": study.get("name"),
      "question": study.get("question"),
      "entity": study.get("entity"),
      "benchmark": study.get("benchmark"),
      "horizon_days": study.get("horizon_days"),
      "embargo_days": study.get("embargo_days"),
      "n_oos": study.get("n_oos"),
      "claim": study.get("claim"),
      "auc": hgb.get("auc"),
      "accuracy": hgb.get("accuracy"),
      "books": books,
      "dm_comparisons": dm_comparisons,
      "dm_summary": stat_tests.get("summary"),
    })
  if not studies:
    return None

  inference = payload.get("inference_summary", {})
  return {
    "generated_at": payload.get("generated_at"),
    "horizon_days": payload.get("horizon_days", 10),
    "cost_bps": payload.get("cost_bps", 10),
    "studies": studies,
    "claims": payload.get("claims") or [],
    "inference_summary": {
      "n_comparisons": inference.get("total_comparisons", 0),
      "bootstrap_replications": inference.get("bootstrap_replications", 2000),
      "confidence_level": inference.get("confidence_level", 0.95),
      "seed": inference.get("random_seed", 42),
    } if inference else None,
    "note": (
      "Cite this purged table for whether the gold-budget / miner-sleeve rules "
      "helped after costs. Confidence intervals and p-values account for serial "
      "dependence via stationary bootstrap and HAC variance. "
      "History charts and paper books use as-of scores with the same embargo grammar."
    ),
  }


def get_research_desk(session: Session) -> dict:
  """Combined institutional research payload."""
  catalog = get_model_catalog(session)
  avg_auc = [
    m["walk_forward"]["mean_auc"]
    for m in catalog
    if m["walk_forward"]["mean_auc"] is not None and not (
      isinstance(m["walk_forward"]["mean_auc"], float) and math.isnan(m["walk_forward"]["mean_auc"])
    )
  ]
  horizons_available = sorted({m["horizon_days"] for m in catalog})

  return {
    "regime_history": get_regime_history(session),
    "macro_series": get_macro_series(session),
    "signal_book": {
      str(h): get_signal_book(session, h)
      for h in (horizons_available or [10])
    },
    "model_catalog": catalog,
    "model_summary": {
      "n_models": len(catalog),
      "mean_auc": round(float(np.mean(avg_auc)), 3) if avg_auc else None,
      "horizons": horizons_available or list(HORIZONS),
      "horizon_labels": {str(h): horizon_label(h) for h in (horizons_available or list(HORIZONS))},
      "horizon_descriptions": {
        str(h): HORIZON_DESCRIPTIONS.get(h, f"{h} trading days")
        for h in (horizons_available or list(HORIZONS))
      },
      "backends": sorted({m["backend"] for m in catalog}),
    },
    "portfolio_analytics": get_portfolio_analytics(session),
    "hypotheses": get_research_hypotheses(),
    "regime_definitions": [
      {
        "id": r.regime_id,
        "name": r.name,
        "gold_bias": r.gold_bias,
        "miner_bias": r.miner_bias,
        "key_drivers": r.key_drivers,
      }
      for r in REGIME_HYPOTHESES
    ],
    "purged_evidence": load_purged_evidence(),
    "integrity": {
      "history_scoring": "asof_embargo",
      "paper_scoring": "asof_embargo",
      "live_scoring": "full_sample_registry",
      "cite": "purged_evidence",
    },
  }
