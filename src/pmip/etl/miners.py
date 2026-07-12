"""Phase 3: Miner fundamental database ETL."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import yfinance as yf
from sqlalchemy.orm import Session

from pmip.constants import ALL_MINERS
from pmip.db.models import MinerCompany, MinerQuarterly
from pmip.db.upsert import upsert

logger = logging.getLogger(__name__)

# Seed quarterly fundamentals (extend with SEC EDGAR / company filings API)
SEED_QUARTERLY: list[dict] = [
  {
    "ticker": "NEM", "quarter_end": "2024-09-30", "production_oz": 1_580_000,
    "aisc_per_oz": 1285, "cash_millions": 3200, "debt_millions": 5400,
    "operating_cash_flow": 890, "free_cash_flow": 420, "reserve_life_years": 12,
    "mine_locations": "Nevada, Peru, Ghana, Australia", "political_risk_score": 0.35,
    "management_guidance": "Maintain production 6M oz annually", "analyst_eps_revision": 0.02,
  },
  {
    "ticker": "AEM", "quarter_end": "2024-09-30", "production_oz": 890_000,
    "aisc_per_oz": 1150, "cash_millions": 1100, "debt_millions": 800,
    "operating_cash_flow": 520, "free_cash_flow": 310, "reserve_life_years": 14,
    "mine_locations": "Canada, Finland, Mexico", "political_risk_score": 0.20,
    "management_guidance": "Record production expected in Q4", "analyst_eps_revision": 0.05,
  },
  {
    "ticker": "B", "quarter_end": "2024-09-30", "production_oz": 1_020_000,
    "aisc_per_oz": 1320, "cash_millions": 2800, "debt_millions": 4200,
    "operating_cash_flow": 650, "free_cash_flow": 280, "reserve_life_years": 10,
    "mine_locations": "Nevada, Tanzania, DRC, Papua New Guinea", "political_risk_score": 0.55,
    "management_guidance": "Focus on Tier 1 assets", "analyst_eps_revision": -0.01,
  },
  {
    "ticker": "KGC", "quarter_end": "2024-09-30", "production_oz": 520_000,
    "aisc_per_oz": 1180, "cash_millions": 680, "debt_millions": 1200,
    "operating_cash_flow": 280, "free_cash_flow": 150, "reserve_life_years": 8,
    "mine_locations": "Russia, Alaska, Mauritania", "political_risk_score": 0.60,
    "management_guidance": "Tasiast expansion on track", "analyst_eps_revision": 0.03,
  },
  {
    "ticker": "AGI", "quarter_end": "2024-09-30", "production_oz": 145_000,
    "aisc_per_oz": 1095, "cash_millions": 320, "debt_millions": 0,
    "operating_cash_flow": 95, "free_cash_flow": 72, "reserve_life_years": 11,
    "mine_locations": "Canada, Mexico", "political_risk_score": 0.25,
    "management_guidance": "Island Gold expansion advancing", "analyst_eps_revision": 0.08,
  },
]


def seed_miner_companies(session: Session) -> int:
  records = [
    {
      "ticker": m["ticker"],
      "name": m["name"],
      "tier": m["tier"],
      "exchange": "NYSE" if m["ticker"] in ("NEM", "B", "KGC", "AGI") else "TSX",
      "is_active": True,
    }
    for m in ALL_MINERS
  ]
  for rec in records:
    existing = session.query(MinerCompany).filter(MinerCompany.ticker == rec["ticker"]).first()
    if not existing:
      session.add(MinerCompany(**rec))
  return len(records)


def upsert_miner_quarterly(session: Session, records: list[dict]) -> int:
  db_records = []
  for row in records:
    db_records.append(
      {
        "ticker": row["ticker"],
        "quarter_end": date.fromisoformat(row["quarter_end"]),
        "production_oz": Decimal(str(row["production_oz"])),
        "aisc_per_oz": Decimal(str(row["aisc_per_oz"])),
        "cash_millions": Decimal(str(row["cash_millions"])),
        "debt_millions": Decimal(str(row["debt_millions"])),
        "operating_cash_flow": Decimal(str(row["operating_cash_flow"])),
        "free_cash_flow": Decimal(str(row["free_cash_flow"])),
        "reserve_life_years": Decimal(str(row["reserve_life_years"])),
        "mine_locations": row.get("mine_locations"),
        "political_risk_score": row.get("political_risk_score"),
        "management_guidance": row.get("management_guidance"),
        "analyst_eps_revision": row.get("analyst_eps_revision"),
      }
    )
  update_keys = [k for k in db_records[0] if k not in ("ticker", "quarter_end")]
  upsert(session, MinerQuarterly, db_records, "uq_miner_ticker_quarter", update_keys)
  return len(db_records)


def fetch_miner_prices(tickers: list[str], period: str = "2y") -> dict[str, float]:
  """Fetch latest prices for miner tickers."""
  prices = {}
  for ticker in tickers:
    try:
      hist = yf.Ticker(ticker).history(period="5d")
      if not hist.empty:
        prices[ticker] = float(hist["Close"].iloc[-1])
    except Exception as e:
      logger.warning("Price fetch failed for %s: %s", ticker, e)
  return prices


def run_miner_etl(session: Session) -> dict[str, int]:
  companies = seed_miner_companies(session)
  quarterly = upsert_miner_quarterly(session, SEED_QUARTERLY)
  logger.info("Seeded %d companies, %d quarterly records", companies, quarterly)
  return {"companies": companies, "quarterly": quarterly}
