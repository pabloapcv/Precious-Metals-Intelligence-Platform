"""Phase 4: Feature engineering for macro and mining signals.

Point-in-time guarantees:
  When building features for a prediction date T, macro data is joined on
  release_date <= T, ensuring we only use values that were actually available
  to a trader on date T. This applies to both live and as-of scoring paths.

  For price-based features (returns, volatility, RSI, etc.), the assumption
  is that daily closes are available by T+1 open (standard market data lag).
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
import ta
from sqlalchemy.orm import Session

from pmip.constants import ALL_MINERS
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
  features[f"{entity}__ret_63d"] = _returns(prices, 63)
  features[f"{entity}__ret_126d"] = _returns(prices, 126)
  features[f"{entity}__vol_20d"] = _volatility(prices, 20)
  features[f"{entity}__vol_63d"] = _volatility(prices, 63)
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


def _load_macro_wide_pit(session: Session, as_of: date | None = None) -> pd.DataFrame:
  """Load macro data as wide DataFrame with point-in-time filtering.

  If as_of is provided, only observations with release_date <= as_of are included,
  using the latest vintage for each (date, symbol). This ensures features built
  for date as_of only use information that was available on that date.
  """
  query = session.query(MacroDaily)
  if as_of:
    query = query.filter(MacroDaily.release_date <= as_of)

  query = query.order_by(MacroDaily.date, MacroDaily.release_date.desc())
  rows = query.all()
  if not rows:
    return pd.DataFrame()

  seen = set()
  filtered_rows = []
  for r in rows:
    key = (r.date, r.symbol)
    if key not in seen:
      seen.add(key)
      filtered_rows.append(r)

  df = pd.DataFrame(
    [{"date": r.date, "symbol": r.symbol, "close": float(r.close)} for r in filtered_rows]
  )
  return df.pivot(index="date", columns="symbol", values="close").sort_index()


def run_feature_engineering(
  session: Session,
  entities: list[str] | None = None,
  on_progress=None,
  as_of: date | None = None,
) -> int:
  """Compute and store all engineered features.

  When as_of is provided, only macro data that was released by that date is used,
  ensuring point-in-time correctness for backfilling historical features.
  """
  wide = _load_macro_wide_pit(session, as_of=as_of)
  if wide.empty:
    logger.warning("No macro data for feature engineering")
    return 0

  wide.index = pd.to_datetime(wide.index)

  total = 0
  target_entities = [e for e in (entities or list(wide.columns)) if e in wide.columns]
  steps = len(target_entities) + 2  # price features + cross-asset + miner block

  def _note(action: str, item: str, detail: str, done: int) -> None:
    if on_progress is None:
      return
    on_progress(
      "features",
      status="running",
      action=action,
      item=item,
      detail=detail,
      done=done,
      total=steps,
      unit="blocks",
    )

  for index, entity in enumerate(target_entities, start=1):
    _note("Price features", entity, f"Returns, volatility, RSI/MACD for {entity}", index - 1)
    feat = engineer_price_features(wide[entity].dropna(), entity)
    total += upsert_features(session, feat, entity)

  _note(
    "Cross-asset features", "MACRO", "Gold ratios, real yield, dollar trend",
    len(target_entities),
  )
  cross = engineer_cross_asset_features(wide)
  total += upsert_features(session, cross, "MACRO")

  miner_ticker_set = {m["ticker"] for m in ALL_MINERS} | {"GDX", "GDXJ", "SIL", "COPX"}
  miner_tickers = [c for c in wide.columns if c in miner_ticker_set]
  _note(
    "Miner features",
    ", ".join(miner_tickers[:6]) + ("…" if len(miner_tickers) > 6 else ""),
    f"Production surprises and beta-to-gold for {len(miner_tickers)} names",
    len(target_entities) + 1,
  )
  miner_feat = engineer_miner_features(wide, miner_tickers, session)
  total += upsert_features(session, miner_feat, "MINERS")

  if on_progress is not None:
    on_progress(
      "features",
      status="running",
      action="Feature store written",
      item=f"{total:,} values",
      detail=f"Stored {total:,} feature values",
      done=steps,
      total=steps,
      unit="blocks",
    )

  logger.info("Engineered %d feature values", total)
  return total


def load_feature_matrix(session: Session, as_of: date | None = None) -> pd.DataFrame:
  """Load features as wide matrix for modeling.

  Note: Features are pre-computed and stored in FeatureDaily. Point-in-time
  correctness for macro-derived features depends on run_feature_engineering
  being called with appropriate as_of constraints during the ETL.

  The as_of filter here limits which feature rows are returned (features
  with date <= as_of), not which macro data went into computing them.
  For true point-in-time feature recomputation at each historical date,
  use build_features_asof() which recomputes features on the fly.
  """
  query = session.query(FeatureDaily)
  if as_of:
    query = query.filter(FeatureDaily.date <= as_of)
  rows = query.order_by(FeatureDaily.date).all()
  if not rows:
    return pd.DataFrame()

  df = pd.DataFrame([
    {"date": r.date, "feature": f"{r.entity}__{r.feature_name}", "value": r.feature_value}
    for r in rows
  ])
  return df.pivot(index="date", columns="feature", values="value").sort_index()


def build_features_asof(session: Session, as_of: date) -> pd.DataFrame:
  """Build features using only macro data available as of a specific date.

  This recomputes features on the fly using point-in-time macro data,
  suitable for as-of scoring where we need to ensure no look-ahead bias.
  Only macro observations with release_date <= as_of are used.

  Returns a wide DataFrame with feature columns, indexed by date, but
  only containing rows up to as_of.
  """
  wide = _load_macro_wide_pit(session, as_of=as_of)
  if wide.empty:
    return pd.DataFrame()

  wide.index = pd.to_datetime(wide.index)
  wide = wide[wide.index <= pd.Timestamp(as_of)]

  all_features = pd.DataFrame(index=wide.index)

  for entity in wide.columns:
    prices = wide[entity].dropna()
    if len(prices) < 20:
      continue
    feat = engineer_price_features(prices, entity)
    for col in feat.columns:
      if col not in all_features.columns:
        all_features[col] = feat[col]

  cross = engineer_cross_asset_features(wide)
  for col in cross.columns:
    if col not in all_features.columns:
      all_features[col] = cross[col]

  return all_features.dropna(how="all")
