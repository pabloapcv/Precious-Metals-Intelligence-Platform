"""Phase 5: Market regime detection using HMM and clustering."""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from pmip.db.models import MacroDaily, MarketRegime
from pmip.db.upsert import upsert
from pmip.research.knowledge_graph import REGIME_HYPOTHESES

logger = logging.getLogger(__name__)

REGIME_NAMES = {r.regime_id: r.name for r in REGIME_HYPOTHESES}


def _build_regime_features(wide: pd.DataFrame) -> pd.DataFrame:
  """Build feature matrix for regime detection."""
  features = pd.DataFrame(index=wide.index)
  if "T10YIE" in wide.columns:
    features["inflation_level"] = wide["T10YIE"]
    features["inflation_trend"] = wide["T10YIE"].diff(20)
  if "US10Y_REAL" in wide.columns:
    features["real_yield"] = wide["US10Y_REAL"]
    features["real_yield_trend"] = wide["US10Y_REAL"].diff(20)
  if "DX-Y.NYB" in wide.columns:
    features["dxy_trend"] = wide["DX-Y.NYB"].pct_change(20)
  if "VIX" in wide.columns:
    features["vix"] = wide["VIX"]
  if "CL=F" in wide.columns:
    features["oil_trend"] = wide["CL=F"].pct_change(20)
  if "GC=F" in wide.columns:
    features["gold_trend"] = wide["GC=F"].pct_change(20)
  if "SPX" in wide.columns:
    features["spx_trend"] = wide["SPX"].pct_change(20)
  if "GDX" in wide.columns and "GC=F" in wide.columns:
    features["miner_gold_spread"] = wide["GDX"].pct_change(20) - wide["GC=F"].pct_change(20)
  return features.dropna(how="all")


def _label_regimes(states: np.ndarray, feature_matrix: np.ndarray, feature_names: list[str]) -> dict[int, str]:
  """Map HMM states to interpretable regime names."""
  state_profiles = {}
  for state in range(int(states.max()) + 1):
    mask = states == state
    if mask.sum() == 0:
      continue
    profile = feature_matrix[mask].mean(axis=0)
    state_profiles[state] = dict(zip(feature_names, profile))

  labels = {}
  for state, profile in state_profiles.items():
    inflation_trend = profile.get("inflation_trend", 0)
    real_yield_trend = profile.get("real_yield_trend", 0)
    dxy_trend = profile.get("dxy_trend", 0)
    vix = profile.get("vix", 15)
    oil_trend = profile.get("oil_trend", 0)
    spx_trend = profile.get("spx_trend", 0)
    miner_spread = profile.get("miner_gold_spread", 0)

    if vix > 25 or oil_trend > 0.05:
      labels[state] = REGIME_NAMES.get(3, "Geopolitical Crisis")
    elif inflation_trend > 0 and real_yield_trend > 0 and dxy_trend > 0:
      labels[state] = REGIME_NAMES.get(1, "Stagflation / Tightening")
    elif spx_trend < -0.03 and real_yield_trend < 0:
      labels[state] = REGIME_NAMES.get(4, "Recession / Rate Cuts")
    elif real_yield_trend < 0 and dxy_trend < 0:
      labels[state] = REGIME_NAMES.get(2, "Easing / Dollar Weak")
    elif miner_spread > 0.02:
      labels[state] = REGIME_NAMES.get(4, "Recession / Rate Cuts")
    else:
      labels[state] = REGIME_NAMES.get(2, "Easing / Dollar Weak")
  return labels


def detect_regimes_hmm(feature_df: pd.DataFrame, n_regimes: int = 4) -> pd.DataFrame:
  """Detect market regimes using Gaussian HMM."""
  feature_df = feature_df.dropna()
  if len(feature_df) < 100:
    logger.warning("Insufficient data for regime detection")
    return pd.DataFrame()

  scaler = StandardScaler()
  X = scaler.fit_transform(feature_df.values)
  model = GaussianHMM(n_components=n_regimes, covariance_type="diag", n_iter=200, random_state=42)
  model.fit(X)
  states = model.predict(X)
  proba = model.predict_proba(X)

  labels = _label_regimes(states, feature_df.values, list(feature_df.columns))
  regime_ids = {r.name: r.regime_id for r in REGIME_HYPOTHESES}

  results = pd.DataFrame(index=feature_df.index)
  results["regime_id"] = [regime_ids.get(labels.get(s, ""), s + 1) for s in states]
  results["regime_name"] = [labels.get(s, f"Regime {s}") for s in states]
  results["confidence"] = proba.max(axis=1)
  return results


def upsert_regimes(session: Session, regime_df: pd.DataFrame, model_version: str = "hmm_v1") -> int:
  records = []
  for dt, row in regime_df.iterrows():
    d = dt.date() if hasattr(dt, "date") else dt
    records.append(
      {
        "date": d,
        "regime_id": int(row["regime_id"]),
        "regime_name": str(row["regime_name"]),
        "confidence": float(row["confidence"]),
        "model_version": model_version,
      }
    )
  if not records:
    return 0
  upsert(
    session,
    MarketRegime,
    records,
    "uq_regime_date",
    ["regime_id", "regime_name", "confidence", "model_version"],
  )
  return len(records)


def run_regime_detection(session: Session) -> int:
  rows = session.query(MacroDaily).order_by(MacroDaily.date).all()
  if not rows:
    return 0
  df = pd.DataFrame([{"date": r.date, "symbol": r.symbol, "close": float(r.close)} for r in rows])
  wide = df.pivot(index="date", columns="symbol", values="close").sort_index()
  wide.index = pd.to_datetime(wide.index)

  feat = _build_regime_features(wide)
  regimes = detect_regimes_hmm(feat)
  count = upsert_regimes(session, regimes)
  logger.info("Detected regimes for %d days", count)
  return count


def get_current_regime(session: Session) -> dict | None:
  row = session.query(MarketRegime).order_by(MarketRegime.date.desc()).first()
  if not row:
    return None
  return {
    "date": row.date.isoformat(),
    "regime_id": row.regime_id,
    "regime_name": row.regime_name,
    "confidence": row.confidence,
  }
