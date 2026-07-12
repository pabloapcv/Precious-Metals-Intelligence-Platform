"""Phase 2: Geopolitical Risk Index from news and event data.

Composite index built from NLP-derived signals. In production, integrate
GDELT, ACLED, and news APIs. This module provides the scoring framework
and a proxy implementation using VIX and oil volatility as risk proxies.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from pmip.db.models import GeopoliticalRisk, MacroDaily
from pmip.db.upsert import upsert

logger = logging.getLogger(__name__)

GPR_COMPONENTS = [
  "conflict_intensity",
  "sanctions_score",
  "oil_disruption",
  "military_escalation",
  "shipping_disruption",
  "trade_restrictions",
  "election_uncertainty",
]

CONFLICT_KEYWORDS = ["war", "invasion", "missile", "airstrike", "casualties", "conflict"]
SANCTIONS_KEYWORDS = ["sanction", "embargo", "blacklist", "export ban", "tariff"]
OIL_KEYWORDS = ["pipeline", "opec", "oil disruption", "refinery", "strait"]
MILITARY_KEYWORDS = ["troops", "mobilization", "nato", "deployment", "military exercise"]
SHIPPING_KEYWORDS = ["red sea", "suez", "shipping lane", "port closure", "houthi"]
TRADE_KEYWORDS = ["trade war", "export restriction", "import ban", "decoupling"]
ELECTION_KEYWORDS = ["election", "ballot", "referendum", "political uncertainty"]


def score_text(text: str, keywords: list[str]) -> float:
  text_lower = text.lower()
  hits = sum(1 for kw in keywords if kw in text_lower)
  return min(hits / max(len(keywords), 1), 1.0)


def compute_gpr_from_news(articles: list[dict]) -> dict[str, float]:
  if not articles:
    return {c: 0.0 for c in GPR_COMPONENTS}

  scores = {c: [] for c in GPR_COMPONENTS}
  for article in articles:
    text = f"{article.get('title', '')} {article.get('body', '')}"
    scores["conflict_intensity"].append(score_text(text, CONFLICT_KEYWORDS))
    scores["sanctions_score"].append(score_text(text, SANCTIONS_KEYWORDS))
    scores["oil_disruption"].append(score_text(text, OIL_KEYWORDS))
    scores["military_escalation"].append(score_text(text, MILITARY_KEYWORDS))
    scores["shipping_disruption"].append(score_text(text, SHIPPING_KEYWORDS))
    scores["trade_restrictions"].append(score_text(text, TRADE_KEYWORDS))
    scores["election_uncertainty"].append(score_text(text, ELECTION_KEYWORDS))

  return {k: float(np.mean(v)) if v else 0.0 for k, v in scores.items()}


def compute_proxy_gpr(session: Session, target_date: date) -> dict[str, float]:
  lookback = target_date - timedelta(days=30)
  rows = (
    session.query(MacroDaily)
    .filter(MacroDaily.date >= lookback, MacroDaily.date <= target_date)
    .filter(MacroDaily.symbol.in_(["VIX", "CL=F", "GC=F"]))
    .all()
  )
  if not rows:
    return {c: 0.3 for c in GPR_COMPONENTS} | {"gpr_index": 0.3}

  df = pd.DataFrame([{"date": r.date, "symbol": r.symbol, "close": float(r.close)} for r in rows])
  wide = df.pivot(index="date", columns="symbol", values="close").sort_index()
  vix_z = (wide["VIX"].iloc[-1] - wide["VIX"].mean()) / (wide["VIX"].std() + 1e-6) if "VIX" in wide else 0
  oil_vol = wide["CL=F"].pct_change(fill_method=None).std() * 100 if "CL=F" in wide else 0

  base = max(0, min(1, 0.3 + 0.15 * vix_z + 0.1 * oil_vol))
  return {
    "conflict_intensity": base * 0.9,
    "sanctions_score": base * 0.7,
    "oil_disruption": min(1, oil_vol / 5),
    "military_escalation": base * 0.8,
    "shipping_disruption": base * 0.5,
    "trade_restrictions": base * 0.6,
    "election_uncertainty": base * 0.4,
    "gpr_index": base,
  }


def upsert_geopolitical_risk(session: Session, target_date: date, scores: dict[str, float]) -> None:
  gpr = scores.get("gpr_index", np.mean([scores.get(c, 0) for c in GPR_COMPONENTS]))
  record = {
    "date": target_date,
    "gpr_index": float(gpr),
    **{c: float(scores.get(c, 0)) for c in GPR_COMPONENTS},
    "source": scores.get("source", "composite"),
  }
  upsert(
    session,
    GeopoliticalRisk,
    [record],
    "uq_geopolitical_date",
    ["gpr_index", *GPR_COMPONENTS, "source"],
  )


def run_geopolitical_etl(session: Session, lookback_days: int = 365) -> int:
  """Compute daily GPR index for lookback window."""
  end = date.today()
  start = end - timedelta(days=lookback_days + 30)
  rows = (
    session.query(MacroDaily)
    .filter(MacroDaily.date >= start, MacroDaily.date <= end)
    .filter(MacroDaily.symbol.in_(["VIX", "CL=F"]))
    .all()
  )
  if not rows:
    return 0

  df = pd.DataFrame([{"date": r.date, "symbol": r.symbol, "close": float(r.close)} for r in rows])
  wide = df.pivot(index="date", columns="symbol", values="close").sort_index()

  records = []
  current = end - timedelta(days=lookback_days)
  while current <= end:
    window = wide.loc[:current].tail(30)
    if window.empty:
      scores = {c: 0.3 for c in GPR_COMPONENTS}
      gpr = 0.3
    else:
      vix_z = 0.0
      if "VIX" in window.columns and len(window["VIX"].dropna()) > 1:
        vix = window["VIX"].dropna()
        vix_z = (vix.iloc[-1] - vix.mean()) / (vix.std() + 1e-6)
      oil_vol = 0.0
      if "CL=F" in window.columns and len(window["CL=F"].dropna()) > 1:
        oil_vol = window["CL=F"].pct_change(fill_method=None).std() * 100
      gpr = max(0, min(1, 0.3 + 0.15 * vix_z + 0.1 * oil_vol))
      scores = {
        "conflict_intensity": gpr * 0.9,
        "sanctions_score": gpr * 0.7,
        "oil_disruption": min(1, oil_vol / 5),
        "military_escalation": gpr * 0.8,
        "shipping_disruption": gpr * 0.5,
        "trade_restrictions": gpr * 0.6,
        "election_uncertainty": gpr * 0.4,
      }
    records.append({
      "date": current,
      "gpr_index": float(gpr),
      **{c: float(scores.get(c, 0)) for c in GPR_COMPONENTS},
      "source": "market_proxy",
    })
    current += timedelta(days=1)

  chunk_size = 100
  for i in range(0, len(records), chunk_size):
    upsert(
      session,
      GeopoliticalRisk,
      records[i : i + chunk_size],
      "uq_geopolitical_date",
      ["gpr_index", *GPR_COMPONENTS, "source"],
    )
  logger.info("Computed GPR for %d days", len(records))
  return len(records)
