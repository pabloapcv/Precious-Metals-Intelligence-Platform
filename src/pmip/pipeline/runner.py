"""End-to-end pipeline runner used by CLI and API."""

from __future__ import annotations

import logging
import math
from datetime import date

import numpy as np

from pmip.constants import ALL_MINERS, HORIZONS, PREDICTION_TARGETS
from pmip.db.session import get_db_session
from pmip.etl.pipeline import run_daily_etl
from pmip.features.engineering import run_feature_engineering
from pmip.models.regime import run_regime_detection
from pmip.models.training import (
  backfill_prediction_history,
  generate_predictions,
  train_and_save_models,
)
from pmip.portfolio.optimizer import optimize_portfolio, save_portfolio_recommendations

logger = logging.getLogger(__name__)


def _json_safe(value):
  """Convert numpy scalars and non-finite floats so FastAPI can serialize the payload."""
  if isinstance(value, dict):
    return {k: _json_safe(v) for k, v in value.items()}
  if isinstance(value, (list, tuple)):
    return [_json_safe(v) for v in value]
  if isinstance(value, (np.floating, float)):
    num = float(value)
    if math.isnan(num) or math.isinf(num):
      return None
    return num
  if isinstance(value, (np.integer,)):
    return int(value)
  if isinstance(value, np.ndarray):
    return _json_safe(value.tolist())
  return value


def run_full_pipeline(
  lookback_days: int = 365 * 2,
  train_entities: list[str] | None = None,
) -> dict:
  """ETL → features → regime → train → predict → portfolio."""
  entities = train_entities or [t["entity"] for t in PREDICTION_TARGETS]
  etl_results = run_daily_etl(lookback_days=lookback_days)
  logger.info("ETL complete")

  train_results = []
  pred_count = 0
  port_count = 0
  feat_count = 0
  regime_count = 0

  with get_db_session() as session:
    feat_count = run_feature_engineering(session)
    logger.info("Features engineered: %d", feat_count)

    regime_count = run_regime_detection(session)
    logger.info("Regimes detected: %d days", regime_count)

    for entity in entities:
      for horizon in HORIZONS:
        result = train_and_save_models(session, entity, horizon=horizon, run_walk_forward=True)
        train_results.append(result)
        logger.info("Model %s h%sd: %s", entity, horizon, result.get("status"))

    pred_count = generate_predictions(session)
    logger.info("Predictions generated: %d", pred_count)

    hist_count = backfill_prediction_history(session, lookback_days=180, step=5)
    logger.info("Historical predictions backfilled: %d", hist_count)

    miner_tickers = [m["ticker"] for m in ALL_MINERS] + ["GDX", "GDXJ", "GLD"]
    portfolio = optimize_portfolio(session, miner_tickers, method="hrp")
    if not portfolio.empty:
      port_count = save_portfolio_recommendations(session, portfolio, date.today())
      logger.info("Portfolio saved: %d positions", port_count)

  return _json_safe({
    "status": "complete",
    "etl": etl_results,
    "features": feat_count,
    "regimes": regime_count,
    "predictions_generated": pred_count,
    "historical_predictions": hist_count,
    "portfolio_positions": port_count,
    "models_trained": len([r for r in train_results if r.get("status") == "trained"]),
    "train_results": train_results,
  })
