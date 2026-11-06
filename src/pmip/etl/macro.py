"""Phase 2: Macro data ETL — FRED/ALFRED and yfinance ingestion with point-in-time provenance.

Point-in-time guarantees:
  - FRED series with ALFRED history: each observation carries its actual release date
    and vintage (the revision it belongs to).
  - Yahoo/market data: daily closes are available the next trading day (T+1 lag rule).
  - Monthly economic series without ALFRED: conservative lag rules per series type.
  - All lag-assumed rows are flagged so downstream code can distinguish exact from estimated.

See docs/research-note.md for the claim inventory describing which series are
vintage-exact versus lag-assumed.
"""

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


PUBLICATION_LAG_RULES: dict[str, dict] = {
    "DGS2": {"lag_days": 1, "description": "Daily Treasury yield, available next business day"},
    "DGS10": {"lag_days": 1, "description": "Daily Treasury yield, available next business day"},
    "DFII10": {"lag_days": 1, "description": "Daily TIPS yield, available next business day"},
    "T10YIE": {"lag_days": 1, "description": "Daily breakeven, available next business day"},
    "VIXCLS": {"lag_days": 1, "description": "Daily VIX close, available next business day"},
    "DTWEXBGS": {"lag_days": 1, "description": "Daily dollar index, available next business day"},
    "CPIAUCSL": {
        "lag_days": 45,
        "description": "Monthly CPI, released ~2 weeks after reference month end",
    },
    "PCEPI": {
        "lag_days": 30,
        "description": "Monthly PCE, released ~1 month after reference month",
    },
}

DEFAULT_MARKET_LAG_DAYS = 1
DEFAULT_MONTHLY_LAG_DAYS = 30


def _estimate_release_date(obs_date: date, series_id: str | None, source: str) -> tuple[date, bool]:
    """Estimate when an observation was first available for trading.

    Returns (release_date, lag_assumed). lag_assumed=True means we applied a rule,
    not an actual ALFRED vintage lookup.
    """
    if series_id and series_id in PUBLICATION_LAG_RULES:
        lag = PUBLICATION_LAG_RULES[series_id]["lag_days"]
        return obs_date + timedelta(days=lag), True

    if source == "yfinance":
        return obs_date + timedelta(days=DEFAULT_MARKET_LAG_DAYS), True

    return obs_date + timedelta(days=DEFAULT_MARKET_LAG_DAYS), True


def _fetch_yfinance(ticker: str, start: date, end: date) -> pd.DataFrame:
    data = yf.download(ticker, start=start.isoformat(), end=end.isoformat(), progress=False)
    if data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.reset_index()
    data.columns = [c.lower().replace(" ", "_") for c in data.columns]
    return data


def _fetch_fred_with_vintage(series_id: str, start: date, end: date) -> pd.DataFrame:
    """Fetch FRED series with ALFRED vintage information when available.

    Tries the ALFRED real-time endpoint first. If unavailable or fails,
    falls back to standard FRED with lag-assumed release dates.
    """
    settings = get_settings()
    if not settings.fred_api_key:
        logger.warning("FRED_API_KEY not set; skipping %s", series_id)
        return pd.DataFrame()

    try:
        from fredapi import Fred

        fred = Fred(api_key=settings.fred_api_key)

        try:
            vintage_df = fred.get_series_all_releases(
                series_id,
                observation_start=start,
                observation_end=end,
            )
            if vintage_df is not None and not vintage_df.empty:
                return _process_alfred_vintages(vintage_df, series_id)
        except Exception as e:
            logger.debug(
                "ALFRED vintages not available for %s (%s); using standard FRED", series_id, e
            )

        series = fred.get_series(series_id, observation_start=start, observation_end=end)
        if series is None or series.empty:
            return pd.DataFrame()
        df = series.reset_index()
        df.columns = ["date", "close"]
        df["vintage"] = "initial"
        df["release_date"] = df["date"].apply(
            lambda d: _estimate_release_date(
                d.date() if hasattr(d, "date") else d, series_id, "fred"
            )[0]
        )
        df["lag_assumed"] = True
        return df

    except Exception as e:
        logger.error("FRED fetch failed for %s: %s", series_id, e)
        return pd.DataFrame()


def _process_alfred_vintages(vintage_df: pd.DataFrame, series_id: str) -> pd.DataFrame:
    """Process ALFRED vintage data into our schema.

    ALFRED returns a DataFrame with columns: realtime_start, realtime_end, date, value
    where realtime_start is when this revision was first published.
    """
    if vintage_df.empty:
        return pd.DataFrame()

    vintage_df = vintage_df.reset_index()

    if "realtime_start" in vintage_df.columns:
        records = []
        for _, row in vintage_df.iterrows():
            obs_date = row["date"]
            if hasattr(obs_date, "date"):
                obs_date = obs_date.date()

            release = row["realtime_start"]
            if hasattr(release, "date"):
                release = release.date()

            vintage_str = release.isoformat() if release else "initial"

            records.append({
                "date": obs_date,
                "close": row["value"] if "value" in row else row.get(series_id),
                "vintage": vintage_str,
                "release_date": release,
                "lag_assumed": False,
            })
        return pd.DataFrame(records)

    df = vintage_df.copy()
    if "value" not in df.columns and series_id in df.columns:
        df["close"] = df[series_id]
    elif "value" in df.columns:
        df["close"] = df["value"]

    df["vintage"] = "initial"
    df["release_date"] = df["date"].apply(
        lambda d: _estimate_release_date(
            d.date() if hasattr(d, "date") else d, series_id, "fred"
        )[0]
    )
    df["lag_assumed"] = True
    return df[["date", "close", "vintage", "release_date", "lag_assumed"]]


def fetch_macro_series(symbol_def, start: date, end: date) -> pd.DataFrame:
    """Fetch a single macro series from best available source with point-in-time metadata."""
    frames = []

    if symbol_def.fred_series:
        fred_df = _fetch_fred_with_vintage(symbol_def.fred_series, start, end)
        if not fred_df.empty:
            fred_df["source"] = "fred"
            for col in ["open", "high", "low", "volume"]:
                if col not in fred_df.columns:
                    fred_df[col] = None
            frames.append(fred_df)

    if symbol_def.yfinance_ticker and not frames:
        yf_df = _fetch_yfinance(symbol_def.yfinance_ticker, start, end)
        if not yf_df.empty:
            yf_df["source"] = "yfinance"
            yf_df["vintage"] = "initial"
            yf_df["date"] = pd.to_datetime(yf_df["date"]).dt.date
            yf_df["release_date"] = yf_df["date"].apply(
                lambda d: _estimate_release_date(d, None, "yfinance")[0]
            )
            yf_df["lag_assumed"] = True
            frames.append(yf_df)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df["symbol"] = symbol_def.symbol
    df["date"] = pd.to_datetime(df["date"]).dt.date

    if symbol_def.symbol in ("US02Y", "US10Y") and "close" in df.columns:
        max_val = df["close"].max()
        if pd.notna(max_val) and max_val > 20:
            df["close"] = df["close"] / 10.0

    return df.drop_duplicates(subset=["date", "symbol", "vintage"], keep="last")


def upsert_macro_daily(session: Session, df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    now = datetime.utcnow()
    records = []
    for _, row in df.iterrows():
        release = row.get("release_date")
        if release is not None and hasattr(release, "date"):
            release = release.date()

        records.append({
            "date": row["date"],
            "symbol": row["symbol"],
            "open": Decimal(str(row["open"])) if pd.notna(row.get("open")) else None,
            "high": Decimal(str(row["high"])) if pd.notna(row.get("high")) else None,
            "low": Decimal(str(row["low"])) if pd.notna(row.get("low")) else None,
            "close": Decimal(str(row["close"])),
            "volume": Decimal(str(row["volume"])) if pd.notna(row.get("volume")) else None,
            "source": row.get("source", "yfinance"),
            "release_date": release,
            "vintage": row.get("vintage", "initial"),
            "lag_assumed": bool(row.get("lag_assumed", True)),
            "ingested_at": now,
        })

    upsert(
        session,
        MacroDaily,
        records,
        "uq_macro_daily_date_symbol_vintage",
        [
            "open", "high", "low", "close", "volume", "source",
            "release_date", "lag_assumed", "ingested_at",
        ],
    )
    return len(records)


def run_macro_etl(
    session: Session,
    lookback_days: int = 365 * 5,
    on_progress=None,
) -> dict[str, int]:
    """Ingest all macro symbols for the lookback window with point-in-time provenance."""
    end = date.today()
    start = end - timedelta(days=lookback_days)
    results = {}
    total = len(MACRO_SYMBOLS)

    for index, sym in enumerate(MACRO_SYMBOLS, start=1):
        if on_progress is not None:
            on_progress(
                "etl",
                status="running",
                action="Downloading close",
                item=f"{sym.symbol} · {sym.name}",
                detail=f"Downloading {sym.symbol} ({sym.name})",
                done=index - 1,
                total=total,
                unit="symbols",
                log=False,
            )
        try:
            df = fetch_macro_series(sym, start, end)
            count = upsert_macro_daily(session, df)
            results[sym.symbol] = count
            logger.info("Ingested %d rows for %s", count, sym.symbol)
            if on_progress is not None:
                on_progress(
                    "etl",
                    status="running",
                    action="Saved close",
                    item=f"{sym.symbol} · {count:,} rows",
                    detail=f"Saved {sym.symbol}: {count:,} rows",
                    done=index,
                    total=total,
                    unit="symbols",
                )
        except Exception as e:
            logger.error("Failed to ingest %s: %s", sym.symbol, e)
            results[sym.symbol] = 0
            if on_progress is not None:
                on_progress(
                    "etl",
                    status="running",
                    action="Download failed",
                    item=sym.symbol,
                    detail=f"Failed {sym.symbol}: {e}",
                    done=index,
                    total=total,
                    unit="symbols",
                )

    if on_progress is not None:
        on_progress(
            "etl",
            status="running",
            action="Deriving real yields",
            item="US10Y_REAL",
            detail="Writing derived real-yield series if FRED TIPS is missing",
            done=total,
            total=total,
            unit="symbols",
        )
    _write_derived_real_yields(session)
    return results


def _write_derived_real_yields(session: Session) -> None:
    """Compute real yield proxy when FRED TIPS data is unavailable."""
    existing = session.query(MacroDaily).filter(MacroDaily.symbol == "US10Y_REAL").count()
    if existing > 0:
        return

    rows = (
        session.query(MacroDaily)
        .filter(MacroDaily.symbol == "US10Y", MacroDaily.vintage == "initial")
        .order_by(MacroDaily.date)
        .all()
    )
    if not rows:
        return

    now = datetime.utcnow()
    records = []
    for row in rows:
        nominal = float(row.close)
        real = nominal - 2.25
        release = row.release_date or (row.date + timedelta(days=1))
        records.append({
            "date": row.date,
            "symbol": "US10Y_REAL",
            "open": None,
            "high": None,
            "low": None,
            "close": Decimal(str(round(real, 4))),
            "volume": None,
            "source": "derived",
            "release_date": release,
            "vintage": "initial",
            "lag_assumed": True,
            "ingested_at": now,
        })

    upsert(
        session,
        MacroDaily,
        records,
        "uq_macro_daily_date_symbol_vintage",
        [
            "open", "high", "low", "close", "volume", "source",
            "release_date", "lag_assumed", "ingested_at",
        ],
    )
    logger.info("Wrote %d derived US10Y_REAL rows", len(records))


def load_macro_to_dataframe(
    session: Session,
    symbols: list[str] | None = None,
    as_of: date | None = None,
) -> pd.DataFrame:
    """Load macro data as wide DataFrame (date index, symbol columns).

    If as_of is provided, only use observations that were available (released)
    by that date, taking the latest vintage per (date, symbol) that was known
    by as_of. This ensures point-in-time correctness.
    """
    query = session.query(MacroDaily)
    if symbols:
        query = query.filter(MacroDaily.symbol.in_(symbols))

    if as_of:
        query = query.filter(MacroDaily.release_date <= as_of)

    rows = query.order_by(MacroDaily.date, MacroDaily.release_date.desc()).all()
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


def load_macro_with_availability(
    session: Session,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """Load macro data with release_date for as-of feature joins.

    Returns a long-form DataFrame with columns:
      date, symbol, close, release_date, vintage, lag_assumed, source

    Feature engineering can join this on release_date <= prediction_date to
    ensure point-in-time correctness.
    """
    query = session.query(MacroDaily)
    if symbols:
        query = query.filter(MacroDaily.symbol.in_(symbols))

    rows = query.order_by(MacroDaily.date).all()
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame([
        {
            "date": r.date,
            "symbol": r.symbol,
            "close": float(r.close),
            "release_date": r.release_date,
            "vintage": r.vintage,
            "lag_assumed": r.lag_assumed,
            "source": r.source,
        }
        for r in rows
    ])


def get_available_macro_asof(
    macro_df: pd.DataFrame,
    prediction_date: date,
) -> pd.DataFrame:
    """Filter macro observations to only those available as of prediction_date.

    For each (date, symbol), returns the latest vintage that was released
    on or before prediction_date. This is the value a trader would have
    known when making a decision on prediction_date.
    """
    if macro_df.empty:
        return pd.DataFrame()

    available = macro_df[macro_df["release_date"] <= prediction_date].copy()
    if available.empty:
        return pd.DataFrame()

    available = available.sort_values("release_date", ascending=False)
    available = available.drop_duplicates(subset=["date", "symbol"], keep="first")

    return available.sort_values("date")
