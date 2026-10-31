"""Point-in-time (as-of) scoring with a horizon embargo.

Live desk models are still fit on the full sample for today's signal.
History charts and paper books use this module instead: at each score date T,
the model is trained only on rows whose forward labels are fully observed by T
(train ends at least ``horizon`` trading days before T).
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sqlalchemy.orm import Session

from pmip.constants import HORIZONS
from pmip.db.models import ModelPrediction
from pmip.db.upsert import upsert
from pmip.features.engineering import load_feature_matrix
from pmip.models.training import _build_price_panel, _create_targets

logger = logging.getLogger(__name__)

# Liquid sleeve used for as-of history and paper (institutional-narrow).
ASOF_ENTITIES = [
  "GLD",
  "IAU",
  "GDX",
  "GDXJ",
  "RING",
  "NEM",
  "AEM",
  "B",
  "KGC",
  "AGI",
  "PAAS",
  "FNV",
  "WPM",
  "FCX",
]

MIN_TRAIN = 60
DEFAULT_TRAIN = 120


def asof_model_version(horizon: int) -> str:
  return f"asof_h{horizon}"


def is_asof_version(version: str | None) -> bool:
  return bool(version) and str(version).startswith("asof_h")


def is_live_version(version: str | None) -> bool:
  """Full-sample desk registry models (not purged as-of history scores)."""
  return not is_asof_version(version)


def scoring_path_for_version(version: str | None) -> str:
  return "asof_embargo" if is_asof_version(version) else "full_sample_live"


def latest_live_prediction(session, *, entity: str, horizon: int):
  """Newest non-as-of prediction row for the live desk."""
  from pmip.db.models import ModelPrediction

  rows = (
    session.query(ModelPrediction)
    .filter(ModelPrediction.entity == entity, ModelPrediction.horizon_days == horizon)
    .order_by(ModelPrediction.date.desc(), ModelPrediction.id.desc())
    .all()
  )
  for row in rows:
    if is_live_version(row.model_version):
      return row
  return None


def latest_live_predictions(session, *, entities: list[str], horizon: int) -> list:
  """Latest live row per entity, sorted by expected alpha descending."""
  from pmip.db.models import ModelPrediction

  rows = (
    session.query(ModelPrediction)
    .filter(
      ModelPrediction.entity.in_(entities),
      ModelPrediction.horizon_days == horizon,
    )
    .order_by(ModelPrediction.date.desc(), ModelPrediction.id.desc())
    .all()
  )
  latest: dict[str, object] = {}
  for row in rows:
    if not is_live_version(row.model_version):
      continue
    if row.entity not in latest:
      latest[row.entity] = row
  return sorted(
    latest.values(),
    key=lambda r: float(getattr(r, "expected_alpha", None) or 0.0),
    reverse=True,
  )


class _Clf:
  def __init__(self, model: HistGradientBoostingClassifier):
    self._model = model

  def predict(self, X: np.ndarray) -> np.ndarray:
    return self._model.predict_proba(X)[:, 1]


class _Reg:
  def __init__(self, model: HistGradientBoostingRegressor):
    self._model = model

  def predict(self, X: np.ndarray) -> np.ndarray:
    return self._model.predict(X)


def _fit_fast(X: np.ndarray, y: np.ndarray, task: str):
  """Small HGB — fast enough to refit on every as-of date."""
  if task == "classification":
    model = HistGradientBoostingClassifier(
      max_iter=40,
      learning_rate=0.08,
      max_depth=3,
      random_state=42,
    )
    model.fit(X, y)
    return _Clf(model)
  model = HistGradientBoostingRegressor(
    max_iter=40,
    learning_rate=0.08,
    max_depth=3,
    random_state=42,
  )
  model.fit(X, y)
  return _Reg(model)


def _trading_score_dates(index: pd.Index, lookback_days: int, step: int) -> list:
  if len(index) == 0:
    return []
  cutoff = index.max() - pd.Timedelta(days=lookback_days)
  window = index[index >= cutoff]
  if len(window) == 0:
    window = index
  dates = list(window[:: max(1, step)])
  if len(window) and window[-1] not in dates:
    dates.append(window[-1])
  return dates


def score_entity_asof(
  features: pd.DataFrame,
  prices: pd.DataFrame,
  entity: str,
  horizon: int,
  score_dates: list,
) -> list[dict]:
  """Fit-and-score ``entity`` at each date with a horizon embargo."""
  if entity not in prices.columns or features.empty:
    return []

  targets = _create_targets(prices, entity, horizon)
  if targets.empty:
    return []

  target_cols = list(targets.columns)
  version = asof_model_version(horizon)
  records: list[dict] = []

  for ts in score_dates:
    if ts not in features.index:
      continue
    pos = features.index.get_loc(ts)
    if isinstance(pos, slice):
      pos = pos.start
    elif isinstance(pos, np.ndarray):
      pos = int(np.flatnonzero(pos)[0])
    pos = int(pos)
    if pos < MIN_TRAIN + horizon:
      continue

    train_end = pos - horizon
    train_start = max(0, train_end - DEFAULT_TRAIN)
    train_idx = features.index[train_start:train_end]
    train = features.loc[train_idx].join(targets, how="inner").dropna()
    if len(train) < MIN_TRAIN:
      continue
    if train["outperform_gold"].nunique() < 2:
      continue

    feat_cols = [c for c in train.columns if c not in target_cols]
    X_train = train[feat_cols].fillna(0).values
    y_class = train["outperform_gold"].values
    y_reg = train["forward_return"].values

    score_cols = [c for c in feat_cols if c in features.columns]
    if not score_cols:
      continue
    X_score = features.loc[[ts], score_cols].fillna(0).values

    try:
      clf = _fit_fast(X_train, y_class, "classification")
      reg = _fit_fast(X_train, y_reg, "regression")
      prob = float(clf.predict(X_score)[0])
      expected = float(reg.predict(X_score)[0])
    except Exception as exc:
      logger.warning("As-of score failed %s h%s @ %s: %s", entity, horizon, ts, exc)
      continue

    d = ts.date() if hasattr(ts, "date") else ts
    records.append({
      "date": d,
      "entity": entity,
      "horizon_days": horizon,
      "prob_outperform_gold": prob,
      "prob_beat_gdx": prob * 0.95,
      "expected_return": expected,
      "expected_alpha": expected - 0.01,
      "model_version": version,
    })

  return records


def backfill_asof_predictions(
  session: Session,
  lookback_days: int | None = None,
  step: int | None = None,
  entities: list[str] | None = None,
  horizons: list[int] | None = None,
  on_progress=None,
) -> int:
  """Write purged as-of scores for history charts and paper books.

  ``step`` defaults to each horizon so paper rebalance dates match the
  economic clock. Pass a smaller step (e.g. 5) for denser history charts.
  Lookback expands automatically for 3m/6m horizons so enough folds exist.
  """
  features = load_feature_matrix(session)
  if features.empty:
    return 0
  prices = _build_price_panel(session)
  target_entities = [e for e in (entities or ASOF_ENTITIES) if e in prices.columns]
  target_horizons = horizons or list(HORIZONS)
  jobs = [(e, h) for e in target_entities for h in target_horizons]
  total = len(jobs)
  count = 0

  for index, (entity, horizon) in enumerate(jobs, start=1):
    use_step = step if step is not None else horizon
    # Need several non-overlapping folds: ~4× horizon, floored at 365 calendar days.
    use_lookback = lookback_days if lookback_days is not None else max(365, horizon * 6)
    score_dates = _trading_score_dates(features.index, use_lookback, use_step)
    if on_progress is not None:
      on_progress(
        "history",
        status="running",
        action="As-of scoring",
        item=f"{entity} · {horizon}d · {len(score_dates)} dates",
        detail=(
          f"Purged as-of fit for {entity} {horizon}d "
          f"({len(score_dates)} dates, embargo={horizon})"
        ),
        done=index - 1,
        total=total,
        unit="models",
        entity=entity,
        horizon=horizon,
      )
    records = score_entity_asof(features, prices, entity, horizon, score_dates)
    if records:
      upsert(
        session,
        ModelPrediction,
        records,
        "uq_prediction",
        ["prob_outperform_gold", "prob_beat_gdx", "expected_return", "expected_alpha"],
      )
      count += len(records)

  session.commit()
  if on_progress is not None:
    on_progress(
      "history",
      status="running",
      action="As-of history written",
      item=f"{count:,} rows",
      detail=f"Wrote {count:,} purged as-of prediction rows",
      done=total,
      total=total,
      unit="models",
    )
  logger.info("As-of backfill wrote %d prediction rows", count)
  return count
