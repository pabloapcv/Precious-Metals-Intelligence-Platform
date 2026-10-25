"""End-to-end pipeline runner used by CLI and API."""

from __future__ import annotations

import logging
import math
from datetime import date

import numpy as np

from pmip.constants import ALL_MINERS, HORIZONS, horizon_label
from pmip.db.session import get_db_session
from pmip.etl.pipeline import run_daily_etl
from pmip.features.engineering import run_feature_engineering
from pmip.models.regime import run_regime_detection
from pmip.models.training import (
  backfill_prediction_history,
  generate_predictions,
  train_and_save_models,
)
from pmip.pipeline.options import PipelineRunConfig, resolve_config
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
  on_progress=None,
  config: PipelineRunConfig | dict | None = None,
) -> dict:
  """Run selected pipeline stages with optional horizon / universe limits."""
  def _progress(stage: str, **kwargs) -> None:
    if on_progress is not None:
      on_progress(stage, **kwargs)

  if isinstance(config, dict):
    cfg = resolve_config(config)
  elif isinstance(config, PipelineRunConfig):
    cfg = config
  else:
    cfg = PipelineRunConfig(lookback_days=lookback_days)
    if train_entities is not None:
      # Preserve legacy callers that pass an explicit entity list via stages=full.
      pass

  if lookback_days != 365 * 2 and config is None:
    cfg.lookback_days = lookback_days

  stages = set(cfg.stages)
  entities = train_entities or cfg.resolved_entities()
  horizons = cfg.horizons or list(HORIZONS)
  model_total = max(1, len(entities) * len(horizons))
  horizon_tag = " · ".join(horizon_label(h) for h in horizons)

  etl_results: dict = {}
  train_results = []
  pred_count = 0
  port_count = 0
  feat_count = 0
  regime_count = 0
  hist_count = 0
  paper_accounts = 0

  if "etl" in stages:
    _progress(
      "etl",
      status="running",
      action="Starting market data",
      item="Yahoo / FRED",
      detail="Fetching prices, flows, and macro series",
      done=0,
      total=0,
      unit="symbols",
    )
    etl_results = run_daily_etl(lookback_days=cfg.lookback_days, on_progress=on_progress)
    logger.info("ETL complete")
    _progress("etl", status="done", detail="Market data saved", action="Market data saved", item="complete")

  needs_session = stages & {"features", "regime", "train", "predict", "history", "portfolio", "paper"}
  if needs_session:
    with get_db_session() as session:
      if "features" in stages:
        _progress(
          "features",
          status="running",
          action="Building feature store",
          item="price · cross-asset · miners",
          detail="Building the feature store",
          done=0,
          total=0,
          unit="blocks",
        )
        feat_count = run_feature_engineering(session, on_progress=on_progress)
        logger.info("Features engineered: %d", feat_count)
        _progress(
          "features",
          status="done",
          detail=f"{feat_count:,} feature values",
          action="Features saved",
          item=f"{feat_count:,} values",
        )

      if "regime" in stages:
        _progress(
          "regime",
          status="running",
          action="Fitting regime model",
          item="HMM",
          detail="Fitting the macro regime",
          done=0,
          total=3,
          unit="steps",
        )
        regime_count = run_regime_detection(session, on_progress=on_progress)
        logger.info("Regimes detected: %d days", regime_count)
        _progress(
          "regime",
          status="done",
          detail=f"{regime_count:,} days",
          action="Regimes saved",
          item=f"{regime_count:,} days",
        )

      if "train" in stages:
        trained = 0
        for index, entity in enumerate(entities):
          for horizon in horizons:
            step = index * len(horizons) + horizons.index(horizon)
            _progress(
              "train",
              status="running",
              action="Training model",
              item=f"{entity} · {horizon_label(horizon)}",
              detail=f"Training {entity} {horizon_label(horizon)}"
              + ("" if cfg.walk_forward else " (no walk-forward)"),
              done=step,
              total=model_total,
              entity=entity,
              horizon=horizon,
              unit="models",
            )
            result = train_and_save_models(
              session,
              entity,
              horizon=horizon,
              run_walk_forward=cfg.walk_forward,
            )
            train_results.append(result)
            if result.get("status") == "trained":
              trained += 1
            logger.info("Model %s h%sd: %s", entity, horizon, result.get("status"))
            _progress(
              "train",
              status="running",
              action="Model saved" if result.get("status") == "trained" else "Skipped model",
              item=f"{entity} · {horizon_label(horizon)}",
              detail=f"{result.get('status', 'unknown')} {entity} {horizon_label(horizon)}",
              done=step + 1,
              total=model_total,
              entity=entity,
              horizon=horizon,
              unit="models",
            )
        _progress(
          "train",
          status="done",
          detail=f"{trained} models",
          done=model_total,
          total=model_total,
          action="Training complete",
          item=f"{trained} models",
          unit="models",
        )

      if "predict" in stages:
        _progress(
          "predict",
          status="running",
          action="Scoring latest day",
          item=horizon_tag,
          detail=f"Scoring the latest day ({horizon_tag})",
          done=0,
          total=model_total,
          unit="models",
        )
        pred_count = generate_predictions(
          session,
          on_progress=on_progress,
          entities=entities,
          horizons=horizons,
        )
        logger.info("Predictions generated: %d", pred_count)
        _progress(
          "predict",
          status="done",
          detail=f"{pred_count} predictions",
          action="Predictions saved",
          item=f"{pred_count} rows",
        )

      if "history" in stages:
        _progress(
          "history",
          status="running",
          action="As-of scoring",
          item=f"liquid · {horizon_tag}",
          detail=f"Purged as-of scoring ({horizon_tag})",
          done=0,
          total=model_total,
          unit="models",
        )
        hist_count = backfill_prediction_history(
          session,
          lookback_days=None,
          step=None,
          entities=entities if cfg.train_scope == "liquid" else None,
          horizons=horizons,
          on_progress=on_progress,
        )
        logger.info("As-of predictions backfilled: %d", hist_count)
        _progress(
          "history",
          status="done",
          detail=f"{hist_count:,} as-of rows",
          action="As-of history saved",
          item=f"{hist_count:,} rows",
        )

      if "portfolio" in stages:
        _progress(
          "portfolio",
          status="running",
          action="Optimizing book",
          item="HRP",
          detail="Building the portfolio with hierarchical risk parity",
          done=0,
          total=2,
          unit="steps",
        )
        miner_tickers = [m["ticker"] for m in ALL_MINERS] + ["GDX", "GDXJ", "GLD"]
        portfolio = optimize_portfolio(session, miner_tickers, method="hrp")
        _progress(
          "portfolio",
          status="running",
          action="Saving weights",
          item=f"{len(portfolio)} names" if not portfolio.empty else "empty",
          detail="Persisting portfolio recommendations",
          done=1,
          total=2,
          unit="steps",
        )
        if not portfolio.empty:
          port_count = save_portfolio_recommendations(session, portfolio, date.today())
          logger.info("Portfolio saved: %d positions", port_count)
        _progress(
          "portfolio",
          status="done",
          detail=f"{port_count} positions",
          action="Portfolio saved",
          item=f"{port_count} positions",
          done=2,
          total=2,
          unit="steps",
        )

      if "paper" in stages:
        from pmip.api.paper_service import run_paper_tests

        _progress(
          "paper",
          status="running",
          action="Marking paper books",
          item=horizon_tag,
          detail=f"Rebuilding paper books ({horizon_tag})",
          done=0,
          total=len(horizons),
          unit="books",
        )
        paper = run_paper_tests(
          session,
          on_progress=on_progress,
          force=True,
          horizons=horizons,
        )
        paper_accounts = len(paper.get("accounts", []))
        _progress(
          "paper",
          status="done",
          detail=f"{paper_accounts} paper books",
          action="Paper books ready",
          item=f"{paper_accounts} books",
        )

  return _json_safe({
    "status": "complete",
    "config": cfg.to_dict(),
    "etl": etl_results,
    "features": feat_count,
    "regimes": regime_count,
    "predictions_generated": pred_count,
    "historical_predictions": hist_count,
    "portfolio_positions": port_count,
    "paper_accounts": paper_accounts,
    "models_trained": len([r for r in train_results if r.get("status") == "trained"]),
    "train_results": train_results,
  })
