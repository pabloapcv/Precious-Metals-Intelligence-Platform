"""Gold versus the rest of the portfolio: keep, add, or reduce.

This is separate from the miner-versus-gold signal book. Miner signals answer
where to sit inside a gold budget. This view answers whether that budget
should be larger or smaller than a plain mix of stocks and cash.
"""

from __future__ import annotations

import math

import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sqlalchemy.orm import Session

from pmip.api.macro_service import build_macro_snapshot
from pmip.db.models import MacroDaily, ModelPrediction
from pmip.features.engineering import load_feature_matrix
from pmip.models.regime import get_current_regime
from pmip.models.training import _build_price_panel
from pmip.research.knowledge_graph import REGIME_HYPOTHESES

HORIZON = 10
_CACHE: dict = {"key": None, "payload": None}


def _finite(value) -> float | None:
  if value is None:
    return None
  try:
    num = float(value)
  except (TypeError, ValueError):
    return None
  if math.isnan(num) or math.isinf(num):
    return None
  return num


def _expected_from_model(features: pd.DataFrame, prices: pd.DataFrame, symbol: str) -> tuple[float | None, str]:
  """10-day expected return for a non-gold asset, fit on the same feature store."""
  if symbol not in prices.columns or features.empty:
    return None, "unavailable"
  forward = prices[symbol].pct_change(HORIZON, fill_method=None).shift(-HORIZON)
  aligned = features.join(forward.rename("y"), how="inner").replace([float("inf"), float("-inf")], pd.NA).dropna()
  if len(aligned) < 60:
    trail = prices[symbol].pct_change(HORIZON).dropna()
    if trail.empty:
      return None, "unavailable"
    return _finite(trail.iloc[-1]), "recent 10-day move"

  y = aligned["y"]
  X = aligned.drop(columns="y")
  keep = X.var().nlargest(min(60, X.shape[1])).index
  X = X[keep].fillna(0)
  model = HistGradientBoostingRegressor(
    max_iter=60,
    learning_rate=0.08,
    max_depth=4,
    random_state=42,
  )
  model.fit(X.values, y.values)
  latest = features.iloc[[-1]]
  for col in keep:
    if col not in latest.columns:
      latest[col] = 0.0
  pred = model.predict(latest[keep].fillna(0).values)[0]
  return _finite(pred), "10-day model"


def _indexed(prices: pd.DataFrame, symbols: list[str], days: int = 120) -> list[dict]:
  frame = prices[ [c for c in symbols if c in prices.columns] ].dropna(how="all").tail(days)
  if frame.empty:
    return []
  base = frame.apply(lambda col: col.dropna().iloc[0] if col.dropna().shape[0] else None)
  rows = []
  for ts, row in frame.iterrows():
    d = ts.date().isoformat() if hasattr(ts, "date") else str(ts)
    point = {"date": d}
    for sym in frame.columns:
      b = base.get(sym)
      val = row.get(sym)
      point[sym] = round(float(val) / float(b) * 100, 2) if b and pd.notna(val) and b != 0 else None
    rows.append(point)
  return rows


def get_allocation(session: Session) -> dict:
  macro = build_macro_snapshot(session)
  gold_row = (
    session.query(ModelPrediction)
    .filter(ModelPrediction.entity == "GLD", ModelPrediction.horizon_days == HORIZON)
    .order_by(ModelPrediction.date.desc())
    .first()
  )
  key = (macro.get("as_of"), gold_row.date.isoformat() if gold_row else None)
  if _CACHE["key"] == key and _CACHE["payload"] is not None:
    return _CACHE["payload"]

  features = load_feature_matrix(session)
  prices = _build_price_panel(session)

  gold_ret = _finite(gold_row.expected_return) if gold_row else None
  gold_method = "gold model, 10-day expected price change"
  if gold_ret is None:
    gold_ret, gold_method = _expected_from_model(features, prices, "GC=F")
    gold_method = f"gold futures, {gold_method}"

  alternatives = [
    ("equities", "S&P 500", "SPX"),
    ("oil", "Oil", "CL=F"),
    ("copper", "Copper", "HG=F"),
  ]
  comparisons = []
  alt_returns: dict[str, float | None] = {}
  for key_name, label, symbol in alternatives:
    ret, method = _expected_from_model(features, prices, symbol)
    alt_returns[key_name] = ret
    spread = (gold_ret - ret) if gold_ret is not None and ret is not None else None
    comparisons.append({
      "id": key_name,
      "label": label,
      "symbol": symbol,
      "expected_return": ret,
      "gold_expected_return": gold_ret,
      "spread": spread,
      "gold_ahead": spread is not None and spread > 0,
      "method": method,
    })

  real_yield = _finite(macro.get("real_yields"))
  dxy_trend = _finite(macro.get("dxy_trend_20d_pct"))
  # dxy_trend_20d_pct is already in percent (2.36 means +2.36%).
  yield_headwind = real_yield is not None and real_yield > 2.0
  yield_support = real_yield is not None and real_yield < 1.0
  dollar_headwind = dxy_trend is not None and dxy_trend > 1.0
  dollar_support = dxy_trend is not None and dxy_trend < -1.0

  equity_spread = next((c["spread"] for c in comparisons if c["id"] == "equities"), None)
  beats_equity = equity_spread is not None and equity_spread > 0
  lags_equity = equity_spread is not None and equity_spread < 0

  regime = get_current_regime(session)
  regime_match = None
  if regime:
    regime_match = next((r for r in REGIME_HYPOTHESES if r.regime_id == regime.get("regime_id")), None)
  gold_bias = regime_match.gold_bias if regime_match else "neutral"
  regime_supports = gold_bias == "bullish" or dollar_support

  if beats_equity and not yield_headwind and not dollar_headwind and regime_supports:
    stance = "add"
  elif lags_equity and (yield_headwind or dollar_headwind):
    stance = "reduce"
  else:
    stance = "keep"

  reasons = _reasons(
    stance=stance,
    gold_ret=gold_ret,
    equity_spread=equity_spread,
    real_yield=real_yield,
    yield_headwind=yield_headwind,
    yield_support=yield_support,
    dxy_trend=dxy_trend,
    dollar_headwind=dollar_headwind,
    dollar_support=dollar_support,
    gold_bias=gold_bias,
    regime_name=regime.get("regime_name") if regime else None,
  )

  payload = {
    "as_of": macro.get("as_of"),
    "horizon_days": HORIZON,
    "stance": stance,
    "summary": reasons["summary"],
    "reasons": reasons["points"],
    "gold_expected_return": gold_ret,
    "gold_method": gold_method,
    "real_yield": real_yield,
    "real_yield_source": macro.get("real_yield_source"),
    "yield_role": "headwind" if yield_headwind else ("support" if yield_support else "neutral"),
    "dollar_trend_20d_pct": dxy_trend,
    "dollar_role": "headwind" if dollar_headwind else ("support" if dollar_support else "neutral"),
    "regime_name": regime.get("regime_name") if regime else None,
    "gold_bias": gold_bias,
    "comparisons": comparisons,
    "relative_prices": _indexed(prices, ["GC=F", "SPX", "CL=F", "HG=F"]),
    "note": (
      "This call is gold versus the rest of a multi-asset book. "
      "It does not change the miner-versus-gold rankings. "
      "A high miner score still only says how to spend the gold budget you keep."
    ),
  }
  _CACHE["key"] = key
  _CACHE["payload"] = payload
  return payload


def _reasons(
  stance: str,
  gold_ret: float | None,
  equity_spread: float | None,
  real_yield: float | None,
  yield_headwind: bool,
  yield_support: bool,
  dxy_trend: float | None,
  dollar_headwind: bool,
  dollar_support: bool,
  gold_bias: str,
  regime_name: str | None,
) -> dict:
  points = []
  if equity_spread is not None:
    if equity_spread > 0:
      points.append(
        f"Over the next {HORIZON} trading days the gold model expects the metal to beat the S&P 500 by {equity_spread * 100:.1f} percentage points."
      )
    else:
      points.append(
        f"Over the next {HORIZON} trading days stocks are expected to beat gold by {abs(equity_spread) * 100:.1f} percentage points."
      )
  if real_yield is not None:
    if yield_headwind:
      points.append(f"Real yields at {real_yield:.2f}% pay you to hold cash and bonds instead of gold. That argues against adding.")
    elif yield_support:
      points.append(f"Real yields at {real_yield:.2f}% are low enough that cash is a weak alternative to gold.")
    else:
      points.append(f"Real yields at {real_yield:.2f}% are neither a clear cost nor a clear gift for holding gold.")
  if dxy_trend is not None:
    if dollar_headwind:
      points.append(f"The dollar is up {dxy_trend:.1f}% over 20 days, which usually leans against gold.")
    elif dollar_support:
      points.append(f"The dollar is down {abs(dxy_trend):.1f}% over 20 days, which usually helps gold.")
  if regime_name:
    points.append(f"The current environment is {regime_name}, where the standing research view on gold is {gold_bias}.")

  if stance == "add":
    summary = "Add. Gold is expected to beat stocks over the next two weeks, and neither real yields nor the dollar are working against it."
  elif stance == "reduce":
    summary = "Reduce. Stocks are expected to beat gold, and high real yields or a stronger dollar weaken the case for holding the same gold budget."
  else:
    summary = "Keep. The case is mixed, so leave the gold budget unchanged. Use the miner rankings only to decide how that budget is split between the metal and the miners."

  if gold_ret is None:
    summary = "Keep. There is not yet a gold return forecast to compare with other markets."
    points.insert(0, "Run the pipeline so gold has a 10-day expected return to set against stocks.")

  return {"summary": summary, "points": points}
