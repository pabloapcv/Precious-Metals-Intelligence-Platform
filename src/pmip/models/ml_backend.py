"""ML backend with LightGBM when available, sklearn fallback otherwise."""

from __future__ import annotations

import logging

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

logger = logging.getLogger(__name__)

LIGHTGBM_AVAILABLE = False

try:
  import lightgbm as lgb

  # Trigger native library load early so we can fall back cleanly on macOS without libomp.
  _ = lgb.__version__
  LIGHTGBM_AVAILABLE = True
except (ImportError, OSError) as exc:
  logger.warning("LightGBM unavailable (%s); using sklearn HistGradientBoosting", exc)


class _SklearnClfWrapper:
  def __init__(self, model: HistGradientBoostingClassifier):
    self._model = model

  def predict(self, X: np.ndarray) -> np.ndarray:
    return self._model.predict_proba(X)[:, 1]


class _SklearnRegWrapper:
  def __init__(self, model: HistGradientBoostingRegressor):
    self._model = model

  def predict(self, X: np.ndarray) -> np.ndarray:
    return self._model.predict(X)


def train_classifier(X_train: np.ndarray, y_train: np.ndarray):
  if LIGHTGBM_AVAILABLE:
    train_set = lgb.Dataset(X_train, label=y_train)
    params = {
      "objective": "binary",
      "metric": "auc",
      "num_leaves": 31,
      "learning_rate": 0.05,
      "feature_fraction": 0.8,
      "bagging_fraction": 0.8,
      "bagging_freq": 5,
      "verbose": -1,
      "seed": 42,
    }
    return lgb.train(params, train_set, num_boost_round=200)

  model = HistGradientBoostingClassifier(
    max_iter=80,
    learning_rate=0.08,
    max_depth=5,
    random_state=42,
  )
  model.fit(X_train, y_train)
  return _SklearnClfWrapper(model)


def train_regressor(X_train: np.ndarray, y_train: np.ndarray):
  if LIGHTGBM_AVAILABLE:
    train_set = lgb.Dataset(X_train, label=y_train)
    params = {
      "objective": "regression",
      "metric": "rmse",
      "num_leaves": 31,
      "learning_rate": 0.05,
      "verbose": -1,
      "seed": 42,
    }
    return lgb.train(params, train_set, num_boost_round=200)

  model = HistGradientBoostingRegressor(
    max_iter=80,
    learning_rate=0.08,
    max_depth=5,
    random_state=42,
  )
  model.fit(X_train, y_train)
  return _SklearnRegWrapper(model)


def predict_classifier(model, X: np.ndarray) -> np.ndarray:
  out = model.predict(X)
  return np.asarray(out, dtype=float)


def predict_regressor(model, X: np.ndarray) -> np.ndarray:
  out = model.predict(X)
  return np.asarray(out, dtype=float)
