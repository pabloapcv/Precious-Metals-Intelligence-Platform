"""Macro data helpers for the dashboard API."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from pmip.db.models import MacroDaily

# Primary symbol with yfinance fallbacks when FRED series are missing.
SYMBOL_FALLBACKS: dict[str, list[str]] = {
  "GC=F": ["GLD"],
  "DX-Y.NYB": ["UUP"],
  "VIX": ["^VIX"],
}


def _latest_close(session: Session, symbol: str) -> float | None:
  row = (
    session.query(MacroDaily)
    .filter(MacroDaily.symbol == symbol)
    .order_by(MacroDaily.date.desc())
    .first()
  )
  if row:
    return float(row.close)
  for alt in SYMBOL_FALLBACKS.get(symbol, []):
    row = (
      session.query(MacroDaily)
      .filter(MacroDaily.symbol == alt)
      .order_by(MacroDaily.date.desc())
      .first()
    )
    if row:
      return float(row.close)
  return None


def _pct_change(session: Session, symbol: str, days: int = 20) -> float | None:
  end = date.today()
  start = end - timedelta(days=days + 10)
  rows = (
    session.query(MacroDaily)
    .filter(MacroDaily.symbol == symbol, MacroDaily.date >= start)
    .order_by(MacroDaily.date)
    .all()
  )
  if len(rows) < 2:
    return None
  first, last = float(rows[0].close), float(rows[-1].close)
  if first == 0:
    return None
  return (last - first) / first


def _estimate_real_yield(session: Session) -> tuple[float | None, str]:
  """Real yield from FRED TIPS, or nominal minus estimated breakeven."""
  real = _latest_close(session, "US10Y_REAL")
  if real is not None:
    return real, "tips"

  nominal = _latest_close(session, "US10Y")
  breakeven = _latest_close(session, "T10YIE")
  if nominal is not None and breakeven is not None:
    return nominal - breakeven, "breakeven_spread"

  if nominal is not None:
    # Long-run breakeven anchor when FRED is unavailable.
    return nominal - 2.25, "estimated"

  return None, "unavailable"


def build_macro_snapshot(session: Session) -> dict:
  real_yield, real_yield_source = _estimate_real_yield(session)
  nominal_10y = _latest_close(session, "US10Y")
  breakeven = _latest_close(session, "T10YIE")
  if breakeven is not None and breakeven > 8:
    breakeven = None
  dxy = _latest_close(session, "DX-Y.NYB")
  vix = _latest_close(session, "VIX")
  gold = _latest_close(session, "GC=F") or _latest_close(session, "GLD")
  silver = _latest_close(session, "SI=F")
  oil = _latest_close(session, "CL=F")
  copper = _latest_close(session, "HG=F")
  spx = _latest_close(session, "SPX")
  gdx = _latest_close(session, "GDX")

  dxy_trend = _pct_change(session, "DX-Y.NYB", 20)
  gold_trend = _pct_change(session, "GC=F", 20) or _pct_change(session, "GLD", 20)

  last_row = session.query(MacroDaily).order_by(MacroDaily.date.desc()).first()
  as_of = last_row.date.isoformat() if last_row else date.today().isoformat()

  # Dynamic macro labels from data
  if real_yield is not None and real_yield > 2.0:
    fed_bias = "hawkish / higher-for-longer"
  elif real_yield is not None and real_yield < 1.0:
    fed_bias = "dovish / easing bias"
  else:
    fed_bias = "neutral"

  if dxy_trend is not None and dxy_trend > 0.02:
    dollar_strength = "strong"
  elif dxy_trend is not None and dxy_trend < -0.02:
    dollar_strength = "weak"
  else:
    dollar_strength = "moderate"

  if breakeven is not None and breakeven > 2.5:
    inflation_label = "elevated"
  elif breakeven is not None and breakeven < 2.0:
    inflation_label = "cooling"
  else:
    inflation_label = "moderate"

  return {
    "as_of": as_of,
    "gold_price": gold,
    "silver_price": silver,
    "oil_price": oil,
    "copper_price": copper,
    "spx": spx,
    "gdx_price": gdx,
    "nominal_10y": nominal_10y,
    "breakeven_10y": breakeven,
    "real_yields": real_yield,
    "real_yield_source": real_yield_source,
    "dxy": dxy,
    "dxy_trend_20d_pct": round(dxy_trend * 100, 2) if dxy_trend is not None else None,
    "gold_trend_20d_pct": round(gold_trend * 100, 2) if gold_trend is not None else None,
    "vix": vix,
    "fed_probability": fed_bias,
    "dollar_strength": dollar_strength,
    "inflation": inflation_label,
  }
