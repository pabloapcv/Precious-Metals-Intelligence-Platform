"""Phase 2: Macro data ETL — FRED and yfinance ingestion."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from pmip.config import get_settings
from pmip.constants import MACRO_SYMBOLS
from pmip.db.models import MacroDaily
from pmip.db.upsert import upsert

logger = logging.getLogger(__name__)


def _fetch_yfinance(ticker: str, start: date, end: date) -> pd.DataFrame:
  data = yf.download(ticker, start=start.isoformat(), end=end.isoformat(), progress=False)
  if data.empty:
    return pd.DataFrame()
  if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)
  data = data.reset_index()
  data.columns = [c.lower().replace(" ", "_") for c in data.columns]
  return data


def _fetch_fred(series_id: str, start: date, end: date) -> pd.DataFrame:
  settings = get_settings()
  if not settings.fred_api_key:
    logger.warning("FRED_API_KEY not set; skipping %s", series_id)
    return pd.DataFrame()
  try:
    from fredapi import Fred

    fred = Fred(api_key=settings.fred_api_key)
    series = fred.get_series(series_id, observation_start=start, observation_end=end)
    if series is None or series.empty:
      return pd.DataFrame()
    df = series.reset_index()
    df.columns = ["date", "close"]
    return df
  except Exception as e:
    logger.error("FRED fetch failed for %s: %s", series_id, e)
    return pd.DataFrame()


def fetch_macro_series(symbol_def, start: date, end: date) -> pd.DataFrame:
  """Fetch a single macro series from best available source."""
  frames = []
  if symbol_def.yfinance_ticker:
    yf_df = _fetch_yfinance(symbol_def.yfinance_ticker, start, end)
    if not yf_df.empty:
      yf_df["source"] = "yfinance"
      frames.append(yf_df)
  if symbol_def.fred_series:
    fred_df = _fetch_fred(symbol_def.fred_series, start, end)
    if not fred_df.empty:
      fred_df["source"] = "fred"
      for col in ["open", "high", "low", "volume"]:
        if col not in fred_df.columns:
          fred_df[col] = None
      frames.append(fred_df)
  if not frames:
    return pd.DataFrame()
  df = pd.concat(frames, ignore_index=True)
  df["symbol"] = symbol_def.symbol
  df["date"] = pd.to_datetime(df["date"]).dt.date
  # ^TNX is sometimes scaled; normalize treasury yields to percent.
  if symbol_def.symbol in ("US02Y", "US10Y") and df["close"].max() > 20:
    df["close"] = df["close"] / 10.0
  return df.drop_duplicates(subset=["date", "symbol"], keep="last")


def upsert_macro_daily(session: Session, df: pd.DataFrame) -> int:
  if df.empty:
    return 0
  records = []
  for _, row in df.iterrows():
    records.append(
      {
        "date": row["date"],
        "symbol": row["symbol"],
        "open": Decimal(str(row["open"])) if pd.notna(row.get("open")) else None,
        "high": Decimal(str(row["high"])) if pd.notna(row.get("high")) else None,
        "low": Decimal(str(row["low"])) if pd.notna(row.get("low")) else None,
        "close": Decimal(str(row["close"])),
        "volume": Decimal(str(row["volume"])) if pd.notna(row.get("volume")) else None,
        "source": row.get("source", "yfinance"),
      }
    )
  upsert(
    session,
    MacroDaily,
    records,
    "uq_macro_daily_date_symbol",
    ["open", "high", "low", "close", "volume", "source"],
  )
  return len(records)


def run_macro_etl(session: Session, lookback_days: int = 365 * 5) -> dict[str, int]:
  """Ingest all macro symbols for the lookback window."""
  end = date.today()
  start = end - timedelta(days=lookback_days)
  results = {}
  for sym in MACRO_SYMBOLS:
    try:
      df = fetch_macro_series(sym, start, end)
      count = upsert_macro_daily(session, df)
      results[sym.symbol] = count
      logger.info("Ingested %d rows for %s", count, sym.symbol)
    except Exception as e:
      logger.error("Failed to ingest %s: %s", sym.symbol, e)
      results[sym.symbol] = 0
  _write_derived_real_yields(session)
  return results


def _write_derived_real_yields(session: Session) -> None:
  """Compute real yield proxy when FRED TIPS data is unavailable."""
  if session.query(MacroDaily).filter(MacroDaily.symbol == "US10Y_REAL").count() > 0:
    return
  rows = (
    session.query(MacroDaily)
    .filter(MacroDaily.symbol == "US10Y")
    .order_by(MacroDaily.date)
    .all()
  )
  if not rows:
    return
  records = []
  for row in rows:
    nominal = float(row.close)
    real = nominal - 2.25
    records.append({
      "date": row.date,
      "symbol": "US10Y_REAL",
      "open": None,
      "high": None,
      "low": None,
      "close": Decimal(str(round(real, 4))),
      "volume": None,
      "source": "derived",
    })
  upsert(
    session,
    MacroDaily,
    records,
    "uq_macro_daily_date_symbol",
    ["open", "high", "low", "close", "volume", "source"],
  )
  logger.info("Wrote %d derived US10Y_REAL rows", len(records))


def load_macro_to_dataframe(session: Session, symbols: list[str] | None = None) -> pd.DataFrame:
  """Load macro data as wide DataFrame (date index, symbol columns)."""
  query = session.query(MacroDaily)
  if symbols:
    query = query.filter(MacroDaily.symbol.in_(symbols))
  rows = query.order_by(MacroDaily.date).all()
  if not rows:
    return pd.DataFrame()
  df = pd.DataFrame(
    [{"date": r.date, "symbol": r.symbol, "close": float(r.close)} for r in rows]
  )
  return df.pivot(index="date", columns="symbol", values="close").sort_index()
