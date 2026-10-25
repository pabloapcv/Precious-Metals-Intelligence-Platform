"""As-of scores must not train on labels that reach into the score date."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pmip.models.asof import score_entity_asof


def test_asof_score_uses_embargoed_training_window():
  n = 200
  idx = pd.bdate_range("2023-01-02", periods=n)
  rng = np.random.default_rng(7)
  prices = pd.DataFrame(
    {
      "GLD": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))),
      "GC=F": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))),
      "GDX": 100 * np.exp(np.cumsum(rng.normal(0, 0.015, n))),
    },
    index=idx,
  )
  features = pd.DataFrame(
    {
      "GLD__ret_20d": prices["GLD"].pct_change(20),
      "GLD__vol_20d": prices["GLD"].pct_change().rolling(20).std(),
      "real_yield": rng.normal(1.5, 0.2, n),
      "dxy_zscore": rng.normal(0, 1, n),
    },
    index=idx,
  ).dropna()

  horizon = 10
  score_dates = [features.index[-30], features.index[-20], features.index[-10]]
  rows = score_entity_asof(features, prices, "GLD", horizon, score_dates)

  assert len(rows) >= 2
  for row in rows:
    assert row["model_version"] == "asof_h10"
    assert 0.0 <= row["prob_outperform_gold"] <= 1.0
    assert row["entity"] == "GLD"


def test_asof_skips_dates_without_enough_history():
  idx = pd.bdate_range("2024-01-02", periods=40)
  prices = pd.DataFrame(
    {"GLD": np.linspace(100, 110, 40), "GC=F": np.linspace(100, 108, 40), "GDX": np.linspace(30, 35, 40)},
    index=idx,
  )
  features = pd.DataFrame({"x": np.linspace(0, 1, 40)}, index=idx)
  rows = score_entity_asof(features, prices, "GLD", horizon=10, score_dates=[idx[20]])
  assert rows == []
