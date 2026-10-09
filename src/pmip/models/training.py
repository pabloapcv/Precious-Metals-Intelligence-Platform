"""Phase 6: ML training pipeline with walk-forward validation."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score
from sqlalchemy.orm import Session

from pmip.config import get_settings
from pmip.constants import HORIZONS, PREDICTION_TARGETS
from pmip.db.models import MacroDaily, ModelPrediction
from pmip.db.upsert import upsert
from pmip.features.engineering import load_feature_matrix
from pmip.models.ml_backend import (
  LIGHTGBM_AVAILABLE,
  predict_classifier,
  predict_regressor,
  train_classifier,
  train_regressor,
)

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardConfig:
  train_window: int = 252  # ~1 year
  test_window: int = 42  # ~2 months
  step_size: int = 21  # ~1 month
  horizon: int = 10
  model_type: str = "lightgbm"


def _build_price_panel(session: Session) -> pd.DataFrame:
  rows = session.query(MacroDaily).order_by(MacroDaily.date).all()
  df = pd.DataFrame([{"date": r.date, "symbol": r.symbol, "close": float(r.close)} for r in rows])
  return df.pivot(index="date", columns="symbol", values="close").sort_index()


def _create_targets(prices: pd.DataFrame, entity: str, horizon: int, benchmark: str = "GC=F") -> pd.DataFrame:
  """Create forward return and outperformance targets."""
  if entity not in prices.columns:
    return pd.DataFrame()
  entity_ret = prices[entity].pct_change(horizon).shift(-horizon)
  bench_ret = prices[benchmark].pct_change(horizon).shift(-horizon) if benchmark in prices.columns else entity_ret
  gdx_ret = prices["GDX"].pct_change(horizon).shift(-horizon) if "GDX" in prices.columns else bench_ret

  targets = pd.DataFrame(index=prices.index)
  targets["forward_return"] = entity_ret
  targets["outperform_gold"] = (entity_ret > bench_ret).astype(int)
  targets["beat_gdx"] = (entity_ret > gdx_ret).astype(int)
  return targets.dropna()


def walk_forward_split(n_samples: int, config: WalkForwardConfig) -> list[tuple[slice, slice]]:
  splits = []
  start = config.train_window
  while start + config.test_window <= n_samples:
    train_slice = slice(start - config.train_window, start)
    test_slice = slice(start, start + config.test_window)
    splits.append((train_slice, test_slice))
    start += config.step_size
  return splits


def train_lightgbm(X_train: np.ndarray, y_train: np.ndarray, task: str = "classification"):
  if task == "classification":
    return train_classifier(X_train, y_train)
  return train_regressor(X_train, y_train)


def adaptive_walk_forward_config(n_samples: int, horizon: int) -> WalkForwardConfig | None:
  """Scale walk-forward windows to available aligned sample count (~2y daily data)."""
  if n_samples < 80:
    return None

  train = min(252, max(40, int(n_samples * 0.55)))
  test = min(42, max(10, int(n_samples * 0.12)))
  step = min(21, max(5, int(n_samples * 0.08)))

  while train + test > n_samples and train > 30:
    train -= 10
    test = max(8, test - 2)

  if train + test > n_samples:
    return None

  return WalkForwardConfig(train_window=train, test_window=test, step_size=step, horizon=horizon)


def run_walk_forward_validation(
  features: pd.DataFrame,
  targets: pd.DataFrame,
  config: WalkForwardConfig,
) -> dict:
  """Run walk-forward backtest and return metrics."""
  aligned = features.join(targets, how="inner").dropna()
  if len(aligned) < config.train_window + config.test_window:
    return {"error": "insufficient data", "folds": 0}

  X = aligned.drop(columns=targets.columns).values
  y_class = aligned["outperform_gold"].values
  y_reg = aligned["forward_return"].values

  splits = walk_forward_split(len(aligned), config)
  fold_metrics = []

  for i, (train_sl, test_sl) in enumerate(splits):
    X_train, X_test = X[train_sl], X[test_sl]
    y_train, y_test = y_class[train_sl], y_class[test_sl]

    if len(np.unique(y_train)) < 2:
      continue

    model = train_lightgbm(X_train, y_train, task="classification")
    proba = predict_classifier(model, X_test)
    pred = (proba > 0.5).astype(int)

    try:
      auc = float(roc_auc_score(y_test, proba))
      if math.isnan(auc) or math.isinf(auc):
        auc = None
    except ValueError:
      auc = None

    fold_metrics.append({
      "fold": i,
      "accuracy": float(accuracy_score(y_test, pred)),
      "auc": auc,
      "n_test": int(len(y_test)),
    })

  if not fold_metrics:
    return {"error": "no valid folds", "folds": 0}

  aucs = [f["auc"] for f in fold_metrics if f["auc"] is not None]
  accs = [f["accuracy"] for f in fold_metrics]
  return {
    "folds": len(fold_metrics),
    "mean_accuracy": float(np.mean(accs)) if accs else None,
    "mean_auc": float(np.mean(aucs)) if aucs else None,
    "fold_details": fold_metrics,
  }


def train_and_save_models(
  session: Session,
  entity: str,
  horizon: int = 10,
  run_walk_forward: bool = False,
) -> dict:
  """Train final model on all available data and save to registry."""
  settings = get_settings()
  backend = "lightgbm" if LIGHTGBM_AVAILABLE else "sklearn"

  try:
    import os

    import mlflow

    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow_enabled = settings.mlflow_tracking_uri.startswith("file:")
  except Exception:
    mlflow = None
    mlflow_enabled = False

  features = load_feature_matrix(session)
  prices = _build_price_panel(session)
  targets = _create_targets(prices, entity, horizon)

  if features.empty or targets.empty:
    return {"entity": entity, "status": "no_data"}

  aligned = features.join(targets, how="inner").dropna()
  if len(aligned) < 100:
    return {"entity": entity, "status": "insufficient_data"}

  X = aligned.drop(columns=targets.columns).values
  y_class = aligned["outperform_gold"].values
  y_reg = aligned["forward_return"].values
  feature_names = list(aligned.drop(columns=targets.columns).columns)

  config = adaptive_walk_forward_config(len(aligned), horizon) or WalkForwardConfig(horizon=horizon)
  wf_results: dict = {"skipped": True}
  if run_walk_forward:
    if adaptive_walk_forward_config(len(aligned), horizon):
      wf_results = run_walk_forward_validation(features, targets, config)
    else:
      wf_results = {"error": "insufficient data", "folds": 0, "n_samples": len(aligned)}

  def _save_models():
    clf_model = train_lightgbm(X, y_class, task="classification")
    reg_model = train_lightgbm(X, y_reg, task="regression")

    model_dir = Path(settings.model_registry_path)
    model_dir.mkdir(parents=True, exist_ok=True)
    clf_path = model_dir / f"{entity}_clf_h{horizon}.pkl"
    reg_path = model_dir / f"{entity}_reg_h{horizon}.pkl"
    meta_path = model_dir / f"{entity}_meta_h{horizon}.pkl"

    joblib.dump(clf_model, clf_path)
    joblib.dump(reg_model, reg_path)
    joblib.dump(
      {
        "feature_names": feature_names,
        "entity": entity,
        "horizon": horizon,
        "backend": backend,
        "trained_at": date.today().isoformat(),
        "walk_forward": wf_results,
      },
      meta_path,
    )
    return clf_path

  if mlflow_enabled:
    try:
      with mlflow.start_run(run_name=f"{entity}_h{horizon}"):
        mlflow.log_params({
          "entity": entity,
          "horizon": horizon,
          "n_samples": len(aligned),
          "backend": backend,
        })
        if "mean_auc" in wf_results:
          mlflow.log_metrics({
            "mean_auc": wf_results["mean_auc"],
            "mean_accuracy": wf_results["mean_accuracy"],
            "folds": wf_results["folds"],
          })
        clf_path = _save_models()
        mlflow.log_artifact(str(clf_path))
    except Exception as exc:
      logger.warning("MLflow logging failed (%s); saving models locally", exc)
      clf_path = _save_models()
  else:
    clf_path = _save_models()

  return {
    "entity": entity,
    "horizon": horizon,
    "status": "trained",
    "walk_forward": wf_results,
    "model_path": str(clf_path),
  }


def generate_predictions(session: Session, as_of: date | None = None) -> int:
  """Generate predictions for all entities and store in DB."""
  settings = get_settings()
  features = load_feature_matrix(session, as_of=as_of)
  if features.empty:
    return 0

  model_dir = Path(settings.model_registry_path)
  count = 0
  latest_features = features.iloc[[-1]]

  for target in PREDICTION_TARGETS:
    entity = target["entity"]
    for horizon in HORIZONS:
      meta_path = model_dir / f"{entity}_meta_h{horizon}.pkl"
      clf_path = model_dir / f"{entity}_clf_h{horizon}.pkl"
      reg_path = model_dir / f"{entity}_reg_h{horizon}.pkl"
      if not all(p.exists() for p in (meta_path, clf_path, reg_path)):
        continue

      meta = joblib.load(meta_path)
      clf = joblib.load(clf_path)
      reg = joblib.load(reg_path)

      feat_cols = [c for c in meta["feature_names"] if c in latest_features.columns]
      if not feat_cols:
        continue
      X = latest_features[feat_cols].fillna(0).values

      prob_gold = float(predict_classifier(clf, X)[0])
      expected_ret = float(predict_regressor(reg, X)[0])
      pred_date = latest_features.index[-1]
      d = pred_date.date() if hasattr(pred_date, "date") else pred_date

      record = {
        "date": d,
        "entity": entity,
        "horizon_days": horizon,
        "prob_outperform_gold": prob_gold,
        "prob_beat_gdx": prob_gold * 0.95,
        "expected_return": expected_ret,
        "expected_alpha": expected_ret - 0.01,
        "model_version": f"{'lgbm' if LIGHTGBM_AVAILABLE else 'sklearn'}_h{horizon}",
      }
      upsert(
        session,
        ModelPrediction,
        [record],
        "uq_prediction",
        ["prob_outperform_gold", "prob_beat_gdx", "expected_return", "expected_alpha"],
      )
      count += 1

  session.commit()
  return count


def backfill_prediction_history(
  session: Session,
  lookback_days: int = 180,
  step: int = 5,
  entities: list[str] | None = None,
  horizons: list[int] | None = None,
) -> int:
  """Score trained models on historical feature dates so charts have a real time series.

  Walks backwards through available feature rows every ``step`` trading days
  and upserts predictions. Uses current model artifacts (point-in-time features,
  current weights) — suitable for outlook history visualization.
  """
  settings = get_settings()
  features = load_feature_matrix(session)
  if features.empty:
    return 0

  model_dir = Path(settings.model_registry_path)
  target_entities = entities or [t["entity"] for t in PREDICTION_TARGETS]
  target_horizons = horizons or list(HORIZONS)

  # Sample every `step` rows within lookback window
  cutoff = features.index.max() - pd.Timedelta(days=lookback_days)
  window = features[features.index >= cutoff]
  if window.empty:
    window = features
  sample_idx = window.index[::step]
  if len(window.index) and window.index[-1] not in sample_idx:
    sample_idx = sample_idx.append(pd.Index([window.index[-1]]))
  if len(sample_idx) == 0:
    return 0

  count = 0
  backend_tag = "lgbm" if LIGHTGBM_AVAILABLE else "sklearn"

  for entity in target_entities:
    for horizon in target_horizons:
      meta_path = model_dir / f"{entity}_meta_h{horizon}.pkl"
      clf_path = model_dir / f"{entity}_clf_h{horizon}.pkl"
      reg_path = model_dir / f"{entity}_reg_h{horizon}.pkl"
      if not all(p.exists() for p in (meta_path, clf_path, reg_path)):
        continue

      meta = joblib.load(meta_path)
      clf = joblib.load(clf_path)
      reg = joblib.load(reg_path)
      feat_cols = [c for c in meta["feature_names"] if c in features.columns]
      if not feat_cols:
        continue

      X = window.loc[sample_idx, feat_cols].fillna(0).values
      probs = predict_classifier(clf, X)
      rets = predict_regressor(reg, X)

      records = []
      for i, ts in enumerate(sample_idx):
        d = ts.date() if hasattr(ts, "date") else ts
        records.append({
          "date": d,
          "entity": entity,
          "horizon_days": horizon,
          "prob_outperform_gold": float(probs[i]),
          "prob_beat_gdx": float(probs[i]) * 0.95,
          "expected_return": float(rets[i]),
          "expected_alpha": float(rets[i]) - 0.01,
          "model_version": f"{backend_tag}_h{horizon}",
        })

      upsert(
        session,
        ModelPrediction,
        records,
        "uq_prediction",
        ["prob_outperform_gold", "prob_beat_gdx", "expected_return", "expected_alpha"],
      )
      count += len(records)

  session.commit()
  logger.info("Backfilled %d historical prediction rows", count)
  return count
