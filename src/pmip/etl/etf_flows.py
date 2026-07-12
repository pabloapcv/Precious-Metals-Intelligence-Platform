"""Phase 2: Gold ETF flow tracking."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from pmip.constants import GOLD_ETFS
from pmip.db.models import ETFFlow
from pmip.db.upsert import upsert

logger = logging.getLogger(__name__)


def _estimate_flows_from_shares(ticker: str, start: date, end: date) -> pd.DataFrame:
  """Estimate ETF flows from shares outstanding changes × NAV."""
  etf = yf.Ticker(ticker)
  hist = etf.history(start=start.isoformat(), end=end.isoformat())
  if hist.empty:
    return pd.DataFrame()

  info = etf.info or {}
  shares = info.get("sharesOutstanding")
  if shares is None:
    # Proxy: use volume-weighted price change as flow indicator
    hist["daily_flow"] = hist["Close"].pct_change() * hist["Volume"] * hist["Close"] / 1e6
  else:
    hist["daily_flow"] = hist["Close"].pct_change().fillna(0) * shares * hist["Close"].mean() / 1e9

  hist = hist.reset_index()
  hist["date"] = pd.to_datetime(hist["Date"]).dt.date
  hist["ticker"] = ticker
  hist["aum"] = hist["Close"] * (shares or 1e8) / 1e9
  return hist[["date", "ticker", "aum", "daily_flow"]]


def compute_rolling_flows(df: pd.DataFrame) -> pd.DataFrame:
  df = df.sort_values("date")
  df["weekly_flow"] = df["daily_flow"].rolling(5, min_periods=1).sum()
  df["flow_30d_avg"] = df["daily_flow"].rolling(30, min_periods=5).mean()
  df["flow_60d_avg"] = df["daily_flow"].rolling(60, min_periods=10).mean()
  return df


def upsert_etf_flows(session: Session, df: pd.DataFrame) -> int:
  if df.empty:
    return 0
  records = []
  for _, row in df.iterrows():
    records.append(
      {
        "date": row["date"],
        "ticker": row["ticker"],
        "aum": Decimal(str(row["aum"])) if pd.notna(row.get("aum")) else None,
        "daily_flow": Decimal(str(row["daily_flow"])) if pd.notna(row.get("daily_flow")) else None,
        "weekly_flow": Decimal(str(row["weekly_flow"])) if pd.notna(row.get("weekly_flow")) else None,
        "flow_30d_avg": Decimal(str(row["flow_30d_avg"])) if pd.notna(row.get("flow_30d_avg")) else None,
        "flow_60d_avg": Decimal(str(row["flow_60d_avg"])) if pd.notna(row.get("flow_60d_avg")) else None,
      }
    )
  upsert(
    session,
    ETFFlow,
    records,
    "uq_etf_flows_date_ticker",
    ["aum", "daily_flow", "weekly_flow", "flow_30d_avg", "flow_60d_avg"],
  )
  return len(records)


def run_etf_flow_etl(session: Session, lookback_days: int = 365 * 2) -> dict[str, int]:
  end = date.today()
  start = end - timedelta(days=lookback_days)
  results = {}
  for ticker in GOLD_ETFS:
    try:
      df = _estimate_flows_from_shares(ticker, start, end)
      df = compute_rolling_flows(df)
      count = upsert_etf_flows(session, df)
      results[ticker] = count
      logger.info("Ingested %d ETF flow rows for %s", count, ticker)
    except Exception as e:
      logger.error("ETF flow ETL failed for %s: %s", ticker, e)
      results[ticker] = 0
  return results
