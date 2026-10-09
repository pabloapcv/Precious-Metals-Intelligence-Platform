"""Historical time series for outlook, signals, regime, and macro drivers."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from pmip.api.research_service import _safe_float, get_macro_series, get_regime_history
from pmip.constants import PREDICTION_TARGETS
from pmip.db.models import ModelPrediction
from pmip.models.training import backfill_prediction_history


LABEL_MAP = {t["entity"]: t for t in PREDICTION_TARGETS}

KEY_ENTITIES = ["GLD", "GDX", "GDXJ", "RING", "NEM", "AEM", "B", "KGC", "AGI"]


def _prediction_series(
  session: Session,
  entity: str,
  horizon: int,
  days: int,
) -> list[dict]:
  cutoff = date.today() - timedelta(days=days)
  rows = (
    session.query(ModelPrediction)
    .filter(
      ModelPrediction.entity == entity,
      ModelPrediction.horizon_days == horizon,
      ModelPrediction.date >= cutoff,
    )
    .order_by(ModelPrediction.date)
    .all()
  )
  # Deduplicate by date (keep latest model_version if multiples)
  by_date: dict[str, dict] = {}
  for r in rows:
    by_date[r.date.isoformat()] = {
      "date": r.date.isoformat(),
      "prob_outperform_gold": _safe_float(r.prob_outperform_gold, None),
      "prob_beat_gdx": _safe_float(r.prob_beat_gdx, None),
      "expected_alpha": _safe_float(r.expected_alpha, None),
      "expected_return": _safe_float(r.expected_return, None),
      "bullish_pct": round(_safe_float(r.prob_outperform_gold, 0.5) * 100, 1),
    }
  return [by_date[k] for k in sorted(by_date)]


def get_history(
  session: Session,
  days: int = 180,
  horizon: int = 10,
  ensure_backfill: bool = True,
) -> dict:
  """Build historical chart payload for the History workspace."""
  # Auto-backfill if we have too few gold outlook points for a useful chart
  gld_count = (
    session.query(ModelPrediction)
    .filter(ModelPrediction.entity == "GLD", ModelPrediction.horizon_days == horizon)
    .count()
  )
  backfilled = 0
  if ensure_backfill and gld_count < 15:
    backfilled = backfill_prediction_history(
      session,
      lookback_days=days,
      step=5,
      entities=KEY_ENTITIES,
      horizons=[horizon],
    )

  outlook: dict[str, list[dict]] = {}
  for entity in KEY_ENTITIES:
    series = _prediction_series(session, entity, horizon, days)
    if series:
      outlook[entity] = series

  gold = outlook.get("GLD", [])
  regime = get_regime_history(session, days=days)
  macro = get_macro_series(
    session,
    symbols=["GC=F", "DX-Y.NYB", "GDX", "US10Y_REAL", "VIX"],
    days=days,
  )

  # Align summary stats for gold outlook
  gold_stats = None
  if gold:
    probs = [p["bullish_pct"] for p in gold if p["bullish_pct"] is not None]
    if probs:
      gold_stats = {
        "latest": probs[-1],
        "min": min(probs),
        "max": max(probs),
        "avg": round(sum(probs) / len(probs), 1),
        "change": round(probs[-1] - probs[0], 1),
        "n_points": len(probs),
      }

  return {
    "as_of": gold[-1]["date"] if gold else date.today().isoformat(),
    "horizon_days": horizon,
    "lookback_days": days,
    "backfilled_rows": backfilled,
    "gold_outlook": gold,
    "gold_stats": gold_stats,
    "entity_outlook": {
      entity: {
        "label": LABEL_MAP.get(entity, {}).get("label", entity),
        "tier": LABEL_MAP.get(entity, {}).get("tier", "unknown"),
        "series": series,
      }
      for entity, series in outlook.items()
    },
    "regime_history": regime,
    "macro_series": macro,
    "available_entities": list(outlook.keys()),
  }
