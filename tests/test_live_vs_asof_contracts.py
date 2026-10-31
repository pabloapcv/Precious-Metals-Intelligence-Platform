"""Contracts: live desk never cites as-of rows; helpers label scoring paths."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from pmip.api.paper_service import GOLD_BUDGET, TOP_N, _signal
from pmip.api.research_service import _classify_signal, get_signal_book
from pmip.models.asof import (
  is_asof_version,
  is_live_version,
  latest_live_prediction,
  scoring_path_for_version,
)


def test_version_helpers_distinguish_paths():
  assert is_asof_version("asof_h10")
  assert is_asof_version("asof_h126")
  assert not is_asof_version("h10")
  assert not is_asof_version("gld_h10_v1")
  assert not is_asof_version(None)
  assert is_live_version("h10")
  assert not is_live_version("asof_h10")
  assert scoring_path_for_version("asof_h10") == "asof_embargo"
  assert scoring_path_for_version("h10") == "full_sample_live"


def test_latest_live_prediction_skips_asof():
  asof = SimpleNamespace(
    entity="GLD",
    horizon_days=10,
    model_version="asof_h10",
    date=date(2026, 10, 20),
    id=2,
    expected_return=0.02,
  )
  live = SimpleNamespace(
    entity="GLD",
    horizon_days=10,
    model_version="h10",
    date=date(2026, 10, 19),
    id=1,
    expected_return=0.01,
  )
  session = MagicMock()
  q = session.query.return_value
  q.filter.return_value.order_by.return_value.all.return_value = [asof, live]
  assert latest_live_prediction(session, entity="GLD", horizon=10) is live


def test_get_signal_book_never_returns_asof():
  asof = SimpleNamespace(
    entity="NEM",
    horizon_days=10,
    model_version="asof_h10",
    date=date(2026, 10, 20),
    id=9,
    prob_outperform_gold=0.9,
    prob_beat_gdx=0.85,
    expected_return=0.05,
    expected_alpha=0.04,
  )
  live = SimpleNamespace(
    entity="NEM",
    horizon_days=10,
    model_version="h10",
    date=date(2026, 10, 18),
    id=8,
    prob_outperform_gold=0.62,
    prob_beat_gdx=0.59,
    expected_return=0.03,
    expected_alpha=0.02,
  )
  session = MagicMock()
  q = session.query.return_value
  q.filter.return_value.order_by.return_value.all.return_value = [asof, live]
  rows = get_signal_book(session, horizon=10)
  assert len(rows) == 1
  assert rows[0]["entity"] == "NEM"
  assert rows[0]["model_version"] == "h10"
  assert rows[0]["scoring_path"] == "full_sample_live"


def test_signal_and_budget_rules_match_prd():
  assert GOLD_BUDGET == {"add": 0.60, "keep": 0.30, "reduce": 0.10}
  assert TOP_N == 8
  assert _classify_signal(0.62, 0.01) == "long"
  assert _classify_signal(0.38, -0.01) == "short"
  assert _classify_signal(0.56, 0.0) == "overweight"
  assert _classify_signal(0.44, 0.0) == "underweight"
  assert _classify_signal(0.5, 0.0) == "neutral"
  assert _signal(0.62, 0.01) == "long"
  assert _signal(0.56, 0.0) == "overweight"


def test_allocation_stance_branches():
  from pmip.api.allocation_service import _reasons

  add = _reasons(
    stance="add",
    gold_ret=0.02,
    equity_spread=0.01,
    real_yield=0.5,
    yield_headwind=False,
    yield_support=True,
    dxy_trend=-1.5,
    dollar_headwind=False,
    dollar_support=True,
    gold_bias="bullish",
    regime_name="Risk-on easing",
  )
  assert add["summary"].startswith("Add.")

  reduce = _reasons(
    stance="reduce",
    gold_ret=-0.01,
    equity_spread=-0.02,
    real_yield=2.5,
    yield_headwind=True,
    yield_support=False,
    dxy_trend=1.5,
    dollar_headwind=True,
    dollar_support=False,
    gold_bias="bearish",
    regime_name="Tightening",
  )
  assert reduce["summary"].startswith("Reduce.")

  keep = _reasons(
    stance="keep",
    gold_ret=0.0,
    equity_spread=0.0,
    real_yield=1.5,
    yield_headwind=False,
    yield_support=False,
    dxy_trend=0.0,
    dollar_headwind=False,
    dollar_support=False,
    gold_bias="neutral",
    regime_name=None,
  )
  assert keep["summary"].startswith("Keep.")
