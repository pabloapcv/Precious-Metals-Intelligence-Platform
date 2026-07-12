"""Phase 7: Portfolio optimization — HRP, mean-variance, risk parity."""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from pmip.db.models import MacroDaily, ModelPrediction, PortfolioRecommendation
from pmip.db.upsert import upsert

logger = logging.getLogger(__name__)


def _get_return_matrix(session: Session, tickers: list[str], lookback: int = 252) -> pd.DataFrame:
  rows = (
    session.query(MacroDaily)
    .filter(MacroDaily.symbol.in_(tickers))
    .order_by(MacroDaily.date)
    .all()
  )
  df = pd.DataFrame([{"date": r.date, "symbol": r.symbol, "close": float(r.close)} for r in rows])
  prices = df.pivot(index="date", columns="symbol", values="close").sort_index()
  returns = prices.pct_change().dropna().tail(lookback)
  return returns


def _hrp_weights(returns: pd.DataFrame) -> pd.Series:
  """Hierarchical Risk Parity allocation."""
  try:
    import riskfolio as rp

    port = rp.HCPortfolio(returns=returns)
    w = port.optimization(model="HRP", codependence="pearson", linkage="single")
    return w.iloc[:, 0]
  except Exception:
    # Fallback: inverse volatility
    vol = returns.std()
    inv_vol = 1 / (vol + 1e-8)
    return inv_vol / inv_vol.sum()


def _mean_variance_weights(returns: pd.DataFrame, expected_returns: pd.Series) -> pd.Series:
  """Mean-variance optimization with long-only constraint."""
  try:
    import cvxpy as cp

    n = len(returns.columns)
    cov = returns.cov().values
    mu = expected_returns.reindex(returns.columns).fillna(returns.mean()).values
    w = cp.Variable(n)
    ret = mu @ w
    risk = cp.quad_form(w, cov)
    prob = cp.Problem(cp.Maximize(ret - 0.5 * risk), [cp.sum(w) == 1, w >= 0])
    prob.solve()
    if w.value is None:
      raise ValueError("Optimization failed")
    weights = pd.Series(w.value, index=returns.columns)
    return weights / weights.sum()
  except Exception:
    return pd.Series(1 / len(returns.columns), index=returns.columns)


def _kelly_weights(expected_returns: pd.Series, vol: pd.Series, fraction: float = 0.25) -> pd.Series:
  """Fractional Kelly sizing with constraints."""
  kelly = expected_returns / (vol**2 + 1e-8)
  kelly = kelly.clip(lower=0)
  if kelly.sum() == 0:
    return pd.Series(1 / len(kelly), index=kelly.index)
  weights = kelly * fraction
  return weights / weights.sum()


def optimize_portfolio(
  session: Session,
  tickers: list[str],
  method: str = "hrp",
  top_n: int = 10,
) -> pd.DataFrame:
  """Optimize portfolio weights using predictions and return history."""
  returns = _get_return_matrix(session, tickers)
  if returns.empty or len(returns.columns) < 2:
    return pd.DataFrame()

  # Get latest predictions for expected returns
  preds = (
    session.query(ModelPrediction)
    .filter(ModelPrediction.entity.in_(tickers), ModelPrediction.horizon_days == 10)
    .order_by(ModelPrediction.date.desc())
    .all()
  )
  expected = pd.Series(
    {p.entity: p.expected_return or 0 for p in preds}
  ).reindex(returns.columns).fillna(returns.mean())

  if method == "mean_variance":
    weights = _mean_variance_weights(returns, expected)
  elif method == "kelly":
    weights = _kelly_weights(expected, returns.std())
  else:
    # Blend HRP with prediction tilt
    hrp = _hrp_weights(returns)
    pred_tilt = expected.rank(pct=True)
    pred_tilt = pred_tilt / pred_tilt.sum()
    weights = 0.6 * hrp + 0.4 * pred_tilt
    weights = weights / weights.sum()

  # Select top N by weight
  top = weights.nlargest(min(top_n, len(weights)))
  top = top / top.sum()

  result = pd.DataFrame({
    "ticker": top.index,
    "weight": top.values,
    "expected_alpha": [expected.get(t, 0) for t in top.index],
  })
  return result.sort_values("weight", ascending=False).reset_index(drop=True)


def save_portfolio_recommendations(
  session: Session,
  portfolio: pd.DataFrame,
  target_date: date,
  method: str = "hrp",
) -> int:
  if portfolio.empty:
    return 0
  records = []
  for rank, (_, row) in enumerate(portfolio.iterrows(), 1):
    records.append({
      "date": target_date,
      "rank": rank,
      "ticker": row["ticker"],
      "weight": float(row["weight"]),
      "expected_alpha": float(row.get("expected_alpha", 0)),
      "method": method,
    })
  upsert(
    session,
    PortfolioRecommendation,
    records,
    "uq_portfolio_date_rank",
    ["ticker", "weight", "expected_alpha", "method"],
  )
  return len(records)
