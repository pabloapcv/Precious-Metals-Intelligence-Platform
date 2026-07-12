"""Phase 4: Feature engineering for macro and mining signals."""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
import ta
from sqlalchemy.orm import Session

from pmip.db.models import FeatureDaily, MacroDaily, MinerQuarterly
from pmip.db.upsert import upsert

logger = logging.getLogger(__name__)


def _returns(series: pd.Series, window: int) -> pd.Series:
  return series.pct_change(window)


def _volatility(series: pd.Series, window: int) -> pd.Series:
  return series.pct_change().rolling(window).std() * np.sqrt(252)


def _distance_from_dma(series: pd.Series, window: int = 200) -> pd.Series:
  dma = series.rolling(window, min_periods=window // 2).mean()
  return (series - dma) / dma


def _zscore(series: pd.Series, window: int = 60) -> pd.Series:
  mean = series.rolling(window).mean()
  std = series.rolling(window).std()
  return (series - mean) / (std + 1e-8)


def engineer_price_features(prices: pd.Series, entity: str) -> pd.DataFrame:
  """Engineer technical features from a price series."""
  features = pd.DataFrame(index=prices.index)
  features[f"{entity}__ret_5d"] = _returns(prices, 5)
  features[f"{entity}__ret_10d"] = _returns(prices, 10)
  features[f"{entity}__ret_20d"] = _returns(prices, 20)
  features[f"{entity}__vol_20d"] = _volatility(prices, 20)
  features[f"{entity}__dist_200dma"] = _distance_from_dma(prices, 200)
  features[f"{entity}__momentum_60d"] = _returns(prices, 60)
  features[f"{entity}__zscore_60d"] = _zscore(prices, 60)

  if len(prices.dropna()) > 30:
    features[f"{entity}__atr_14"] = ta.volatility.average_true_range(
      prices, prices, prices, window=14
    ) / prices
    features[f"{entity}__rsi_14"] = ta.momentum.rsi(prices, window=14) / 100
    macd = ta.trend.MACD(prices)
    features[f"{entity}__macd"] = macd.macd_diff() / prices

  return features


def engineer_cross_asset_features(wide: pd.DataFrame) -> pd.DataFrame:
  """Engineer ratio and spread features across assets."""
  features = pd.DataFrame(index=wide.index)
  gold = wide.get("GC=F", wide.get("GLD"))
  if gold is None:
    return features

  for col, name in [("CL=F", "gold_oil"), ("HG=F", "gold_copper"), ("SPX", "gold_spx")]:
    if col in wide.columns:
      features[f"{name}_ratio"] = gold / wide[col]
      features[f"{name}_ratio_zscore"] = _zscore(gold / wide[col])

  if "US10Y_REAL" in wide.columns:
    features["real_yield"] = wide["US10Y_REAL"]
    features["real_yield_trend_20d"] = wide["US10Y_REAL"].diff(20)
    features["real_yield_zscore"] = _zscore(wide["US10Y_REAL"])

  if "DX-Y.NYB" in wide.columns:
    features["dxy_trend_20d"] = wide["DX-Y.NYB"].pct_change(20)
    features["dxy_zscore"] = _zscore(wide["DX-Y.NYB"])

  if "VIX" in wide.columns:
    features["vix_level"] = wide["VIX"]
    features["vix_zscore"] = _zscore(wide["VIX"])

  if "T10YIE" in wide.columns:
    features["breakeven_inflation"] = wide["T10YIE"]
    features["inflation_trend_20d"] = wide["T10YIE"].diff(20)

  return features


def engineer_miner_features(
  wide: pd.DataFrame, miner_tickers: list[str], session: Session
) -> pd.DataFrame:
  """Engineer miner-specific fundamental surprise features."""
  features = pd.DataFrame(index=wide.index)
  quarterly = session.query(MinerQuarterly).all()
  if not quarterly:
    return features

  qdf = pd.DataFrame(
    [
      {
        "ticker": q.ticker,
        "quarter_end": q.quarter_end,
        "production_oz": float(q.production_oz or 0),
        "aisc_per_oz": float(q.aisc_per_oz or 0),
        "analyst_eps_revision": float(q.analyst_eps_revision or 0),
      }
      for q in quarterly
    ]
  )

  for ticker in miner_tickers:
    if ticker not in wide.columns:
      continue
    tq = qdf[qdf["ticker"] == ticker].sort_values("quarter_end")
    if len(tq) >= 2:
      prod_surprise = tq["production_oz"].pct_change().iloc[-1]
      aisc_surprise = -tq["aisc_per_oz"].pct_change().iloc[-1]  # lower AISC = positive
      rev_momentum = tq["analyst_eps_revision"].iloc[-1]
      last_date = wide.index[-1]
      features.loc[last_date, f"{ticker}__prod_surprise"] = prod_surprise
      features.loc[last_date, f"{ticker}__aisc_surprise"] = aisc_surprise
      features.loc[last_date, f"{ticker}__revision_momentum"] = rev_momentum

    if "GC=F" in wide.columns and ticker in wide.columns:
      features[f"{ticker}__beta_to_gold_60d"] = (
        wide[ticker].pct_change().rolling(60).cov(wide["GC=F"].pct_change())
        / (wide["GC=F"].pct_change().rolling(60).var() + 1e-8)
      )

  return features


def upsert_features(session: Session, feature_df: pd.DataFrame, entity: str) -> int:
  records = []
  for dt, row in feature_df.iterrows():
    d = dt.date() if hasattr(dt, "date") else dt
    for col, val in row.items():
      if pd.notna(val) and np.isfinite(val):
        ent = col.split("__")[0] if "__" in col else entity
        fname = col.split("__")[-1] if "__" in col else col
        records.append(
          {"date": d, "entity": ent, "feature_name": fname, "feature_value": float(val)}
        )
  if not records:
    return 0
  upsert(session, FeatureDaily, records, "uq_features_daily", ["feature_value"])
  return len(records)


def run_feature_engineering(session: Session, entities: list[str] | None = None) -> int:
  """Compute and store all engineered features."""
  rows = session.query(MacroDaily).order_by(MacroDaily.date).all()
  if not rows:
    logger.warning("No macro data for feature engineering")
    return 0

  df = pd.DataFrame([{"date": r.date, "symbol": r.symbol, "close": float(r.close)} for r in rows])
  wide = df.pivot(index="date", columns="symbol", values="close").sort_index()
  wide.index = pd.to_datetime(wide.index)

  total = 0
  target_entities = entities or list(wide.columns)
  for entity in target_entities:
    if entity in wide.columns:
      feat = engineer_price_features(wide[entity].dropna(), entity)
      total += upsert_features(session, feat, entity)

  cross = engineer_cross_asset_features(wide)
  total += upsert_features(session, cross, "MACRO")

  miner_tickers = [c for c in wide.columns if c in ("NEM", "AEM", "B", "KGC", "AGI", "GDX", "GDXJ")]
  miner_feat = engineer_miner_features(wide, miner_tickers, session)
  total += upsert_features(session, miner_feat, "MINERS")

  logger.info("Engineered %d feature values", total)
  return total


def load_feature_matrix(session: Session, as_of: date | None = None) -> pd.DataFrame:
  """Load features as wide matrix for modeling."""
  query = session.query(FeatureDaily)
  if as_of:
    query = query.filter(FeatureDaily.date <= as_of)
  rows = query.order_by(FeatureDaily.date).all()
  if not rows:
    return pd.DataFrame()

  df = pd.DataFrame(
    [{"date": r.date, "feature": f"{r.entity}__{r.feature_name}", "value": r.feature_value} for r in rows]
  )
  return df.pivot(index="date", columns="feature", values="value").sort_index()
