"""Three separate $100k paper books, one per forecast horizon.

Each book rebalances on its own clock. The 5-day book trades every 5 trading
days using only the 5-day forecasts stored that day. The 10- and 20-day books
do the same with their own models. They never share positions.
"""

from __future__ import annotations

import math
from datetime import date, datetime

import pandas as pd
from sqlalchemy.orm import Session

from pmip.constants import HORIZONS, horizon_label
from pmip.db.models import (
  Base,
  MacroDaily,
  MarketRegime,
  ModelPrediction,
  PaperAccount,
  PaperNav,
  PaperOrder,
  PaperPosition,
)
from pmip.db.session import get_engine
from pmip.research.knowledge_graph import REGIME_HYPOTHESES

STARTING_CASH = 100_000.0
COST_BPS = 10.0
GOLD_BUDGET = {"add": 0.60, "keep": 0.30, "reduce": 0.10}
TOP_N = 8
NOTE = (
  "Each horizon is its own $100,000 account (5d, 10d, 1m, 3m, 6m). On a rebalance "
  "day the book reads the purged as-of forecast stored that day for that horizon "
  "only — the model behind that score was fit with a horizon embargo, so forward "
  "labels that would reach into the rebalance date were excluded. Add puts 60% in "
  "the gold sleeve, Keep 30%, Reduce 10%, and the rest in the S&P 500. The gold "
  "sleeve equal-weights liquid names marked long or overweight, up to eight. "
  "Trades use that day's close and pay 10 basis points on the dollars traded. "
  "Live desk signals still use full-sample models; this path tests the as-of scores only."
)


def _signal(prob: float, alpha: float) -> str:
  if prob >= 0.6 and alpha > 0:
    return "long"
  if prob <= 0.4 and alpha < 0:
    return "short"
  if prob >= 0.55:
    return "overweight"
  if prob <= 0.45:
    return "underweight"
  return "neutral"


def _stance(gold_ret, spx_trail, real_yield, dxy_20, gold_bias: str) -> str:
  beats = gold_ret is not None and spx_trail is not None and gold_ret > spx_trail
  lags = gold_ret is not None and spx_trail is not None and gold_ret < spx_trail
  yield_headwind = real_yield is not None and real_yield > 2
  dollar_headwind = dxy_20 is not None and dxy_20 > 1
  dollar_support = dxy_20 is not None and dxy_20 < -1
  regime_supports = gold_bias == "bullish" or dollar_support
  if beats and not yield_headwind and not dollar_headwind and regime_supports:
    return "add"
  if lags and (yield_headwind or dollar_headwind):
    return "reduce"
  return "keep"


def _finite(value) -> float | None:
  if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
    return None
  try:
    return float(value)
  except (TypeError, ValueError):
    return None


def _ensure_schema() -> None:
  Base.metadata.create_all(bind=get_engine())


def _as_date(day) -> date:
  if isinstance(day, datetime):
    return day.date()
  if isinstance(day, date):
    return day
  if hasattr(day, "date"):
    return day.date()
  return day


def _load_market(session: Session) -> tuple[pd.DataFrame, dict[date, str], dict]:
  from pmip.models.asof import is_asof_version

  rows = session.query(MacroDaily).order_by(MacroDaily.date).all()
  frame = pd.DataFrame([{"date": r.date, "symbol": r.symbol, "close": float(r.close)} for r in rows])
  prices = frame.pivot(index="date", columns="symbol", values="close").sort_index()
  bias = {item.regime_id: item.gold_bias for item in REGIME_HYPOTHESES}
  regimes: dict[date, str] = {}
  for row in session.query(MarketRegime).order_by(MarketRegime.date).all():
    regimes[row.date] = bias.get(row.regime_id, "neutral")
  preds: dict[tuple, dict] = {}
  for row in (
    session.query(ModelPrediction)
    .filter(ModelPrediction.horizon_days.in_(list(HORIZONS)))
    .order_by(ModelPrediction.id.asc())
    .all()
  ):
    # Paper books only trade purged as-of scores — never full-sample backfill.
    if not is_asof_version(row.model_version):
      continue
    preds[(row.date, row.horizon_days, row.entity)] = {
      "prob": _finite(row.prob_outperform_gold) or 0.5,
      "alpha": _finite(row.expected_alpha) or 0.0,
      "ret": _finite(row.expected_return),
    }
  return prices, regimes, preds


def clear_paper_books(session: Session, horizons: list[int] | None = None) -> None:
  """Drop paper rows so the next run rebuilds from current as-of scores.

  If ``horizons`` is set, only those accounts (and their child rows) are removed.
  """
  _ensure_schema()
  if horizons is None:
    for model in (PaperOrder, PaperNav, PaperPosition, PaperAccount):
      session.query(model).delete()
  else:
    accounts = (
      session.query(PaperAccount)
      .filter(PaperAccount.horizon_days.in_(list(horizons)))
      .all()
    )
    ids = [account.id for account in accounts]
    if ids:
      session.query(PaperOrder).filter(PaperOrder.account_id.in_(ids)).delete(synchronize_session=False)
      session.query(PaperNav).filter(PaperNav.account_id.in_(ids)).delete(synchronize_session=False)
      session.query(PaperPosition).filter(PaperPosition.account_id.in_(ids)).delete(synchronize_session=False)
      session.query(PaperAccount).filter(PaperAccount.id.in_(ids)).delete(synchronize_session=False)
  session.commit()


def _price(prices: pd.DataFrame, day, symbol: str) -> float | None:
  if symbol not in prices.columns:
    return None
  series = prices[symbol].loc[:day].dropna()
  if series.empty:
    return None
  return float(series.iloc[-1])


def _sleeve(preds: dict, day, horizon: int, prices: pd.DataFrame) -> dict[str, float]:
  ranked = []
  for (pred_day, pred_h, entity), payload in preds.items():
    if pred_day != day or pred_h != horizon:
      continue
    if entity in ("SPX", "GC=F"):
      continue
    if _price(prices, day, entity) is None:
      continue
    label = _signal(payload["prob"], payload["alpha"])
    if label in ("long", "overweight"):
      ranked.append((payload["alpha"], entity))
  ranked.sort(reverse=True)
  chosen = [entity for _, entity in ranked[:TOP_N]]
  if not chosen:
    fallback = "GLD" if _price(prices, day, "GLD") else "GC=F"
    if _price(prices, day, fallback) is None:
      return {}
    return {fallback: 1.0}
  weight = 1 / len(chosen)
  return {entity: weight for entity in chosen}


def _context(prices: pd.DataFrame, regimes: dict, preds: dict, day, horizon: int) -> tuple[str, float]:
  gold = preds.get((day, horizon, "GLD"), {})
  gold_ret = gold.get("ret")
  spx_trail = None
  if "SPX" in prices.columns:
    window = prices["SPX"].loc[:day].dropna()
    if len(window) > horizon and window.iloc[-1 - horizon]:
      spx_trail = float(window.iloc[-1] / window.iloc[-1 - horizon] - 1)
  real = None
  if "US10Y_REAL" in prices.columns:
    real_series = prices["US10Y_REAL"].loc[:day].dropna()
    if not real_series.empty:
      real = float(real_series.iloc[-1])
  dxy_20 = None
  if "DX-Y.NYB" in prices.columns:
    dxy = prices["DX-Y.NYB"].loc[:day].dropna()
    if len(dxy) > 20 and dxy.iloc[-21]:
      dxy_20 = float(dxy.iloc[-1] / dxy.iloc[-21] - 1) * 100
  prior = [item for item in regimes.items() if item[0] <= day]
  gold_bias = prior[-1][1] if prior else "neutral"
  stance = _stance(gold_ret, spx_trail, real, dxy_20, gold_bias)
  return stance, GOLD_BUDGET[stance]


def _mark(positions: dict[str, float], cash: float, prices: pd.DataFrame, day) -> float:
  total = cash
  for symbol, shares in positions.items():
    px = _price(prices, day, symbol)
    if px is not None:
      total += shares * px
  return total


def _rebalance(positions, cash, prices, day, targets) -> tuple[dict, float, list[dict]]:
  orders = []
  valued = {}
  for symbol in set(positions) | set(targets):
    px = _price(prices, day, symbol)
    if px is None or px <= 0:
      continue
    valued[symbol] = (positions.get(symbol, 0.0), px, targets.get(symbol, 0.0))

  for symbol, (shares, px, target) in valued.items():
    current = shares * px
    if current - target < 1:
      continue
    sell_shares = min(shares, (current - target) / px)
    if sell_shares <= 0:
      continue
    proceeds = sell_shares * px
    fee = proceeds * COST_BPS / 10_000
    positions[symbol] = shares - sell_shares
    cash += proceeds - fee
    orders.append({
      "date": day, "symbol": symbol, "side": "sell", "shares": sell_shares,
      "price": px, "dollars": proceeds, "fee": fee, "reason": "rebalance",
    })

  for symbol, (shares, px, target) in valued.items():
    current = positions.get(symbol, 0.0) * px
    if target - current < 1:
      continue
    dollars = min(target - current, cash / (1 + COST_BPS / 10_000))
    if dollars < 1:
      continue
    fee = dollars * COST_BPS / 10_000
    buy_shares = dollars / px
    positions[symbol] = positions.get(symbol, 0.0) + buy_shares
    cash -= dollars + fee
    orders.append({
      "date": day, "symbol": symbol, "side": "buy", "shares": buy_shares,
      "price": px, "dollars": dollars, "fee": fee, "reason": "rebalance",
    })
  return positions, cash, orders


def _simulate(prices, regimes, preds, horizon: int) -> dict | None:
  if "GC=F" not in prices.columns or "SPX" not in prices.columns:
    return None
  calendar = [_as_date(day) for day in prices.index if pd.notna(prices.at[day, "GC=F"]) and pd.notna(prices.at[day, "SPX"])]
  prices = prices.copy()
  prices.index = [_as_date(day) for day in prices.index]
  pred_days = {day for (day, pred_h, _entity) in preds if pred_h == horizon}
  start_at = next((i for i, day in enumerate(calendar) if day in pred_days), None)
  if start_at is None:
    return None

  positions: dict[str, float] = {}
  cash = STARTING_CASH
  orders: list[dict] = []
  nav_rows: list[dict] = []
  last_i = None
  stance = "keep"
  gold_budget = GOLD_BUDGET["keep"]
  gold_px0 = _price(prices, calendar[start_at], "GLD") or _price(prices, calendar[start_at], "GC=F")
  spx0 = _price(prices, calendar[start_at], "SPX")
  gold_symbol = "GLD" if _price(prices, calendar[start_at], "GLD") else "GC=F"

  for i in range(start_at, len(calendar)):
    day = _as_date(calendar[i])
    due = last_i is None or (i - last_i) >= horizon
    if due and day in pred_days:
      nav_now = _mark(positions, cash, prices, day) if last_i is not None else STARTING_CASH
      stance, gold_budget = _context(prices, regimes, preds, day, horizon)
      sleeve = _sleeve(preds, day, horizon, prices)
      targets = {symbol: nav_now * gold_budget * weight for symbol, weight in sleeve.items()}
      targets["SPX"] = nav_now * (1 - gold_budget)
      positions, cash, batch = _rebalance(positions, cash, prices, day, targets)
      orders.extend(batch)
      last_i = i
    nav = _mark(positions, cash, prices, day)
    gold_px = _price(prices, day, gold_symbol) or gold_px0
    spx_px = _price(prices, day, "SPX") or spx0
    nav_rows.append({
      "date": day,
      "nav": nav,
      "cash": cash,
      "stance": stance,
      "gold_budget": gold_budget,
      "benchmark_gold": STARTING_CASH * (gold_px / gold_px0),
      "benchmark_spx": STARTING_CASH * (spx_px / spx0),
    })

  positions = {symbol: shares for symbol, shares in positions.items() if shares > 1e-8}
  return {"positions": positions, "orders": orders, "nav": nav_rows, "inception": calendar[start_at]}


def _persist(session: Session, horizon: int, result: dict) -> None:
  account = PaperAccount(
    horizon_days=horizon,
    starting_cash=STARTING_CASH,
    cost_bps=COST_BPS,
    inception=result["inception"],
    note=NOTE,
  )
  session.add(account)
  session.flush()
  last = result["nav"][-1]
  for symbol, shares in result["positions"].items():
    px = next((order["price"] for order in reversed(result["orders"]) if order["symbol"] == symbol and order["side"] == "buy"), last["nav"])
    session.add(PaperPosition(account_id=account.id, symbol=symbol, shares=shares, avg_cost=px))
  session.add_all([
    PaperOrder(account_id=account.id, **order)
    for order in result["orders"]
  ])
  session.add_all([
    PaperNav(account_id=account.id, **row)
    for row in result["nav"]
  ])


def _stats(nav_rows: list[PaperNav]) -> dict:
  values = [row.nav for row in nav_rows]
  peak = values[0]
  max_dd = 0.0
  for value in values:
    peak = max(peak, value)
    max_dd = min(max_dd, value / peak - 1)
  last = nav_rows[-1]
  return {
    "as_of": last.date.isoformat(),
    "nav": round(last.nav, 2),
    "total_return": round(last.nav / STARTING_CASH - 1, 4),
    "max_drawdown": round(max_dd, 4),
    "benchmark_gold": round(last.benchmark_gold, 2),
    "benchmark_gold_return": round(last.benchmark_gold / STARTING_CASH - 1, 4),
    "benchmark_spx": round(last.benchmark_spx, 2),
    "benchmark_spx_return": round(last.benchmark_spx / STARTING_CASH - 1, 4),
    "stance": last.stance,
    "gold_budget": last.gold_budget,
    "cash": round(last.cash, 2),
  }


def run_paper_tests(
  session: Session,
  on_progress=None,
  *,
  force: bool = False,
  horizons: list[int] | None = None,
) -> dict:
  """Build paper books from as-of forecasts for the selected horizons."""
  _ensure_schema()
  target_horizons = [int(h) for h in (horizons or list(HORIZONS)) if int(h) in HORIZONS]
  if not target_horizons:
    target_horizons = list(HORIZONS)

  existing = {
    row.horizon_days
    for row in session.query(PaperAccount.horizon_days).filter(PaperAccount.horizon_days.in_(target_horizons))
  }
  if force and existing:
    clear_paper_books(session, target_horizons)
    existing = set()

  missing = [h for h in target_horizons if h not in existing]
  if not missing:
    if on_progress is not None:
      on_progress(
        "paper",
        status="running",
        action="Paper books ready",
        item="cached",
        detail="Reusing existing paper books",
        done=len(target_horizons),
        total=len(target_horizons),
        unit="books",
      )
    return get_paper(session)

  if on_progress is not None:
    on_progress(
      "paper",
      status="running",
      action="Loading market",
      item="prices · regimes · forecasts",
      detail="Loading prices, regimes, and forecasts for paper simulation",
      done=0,
      total=len(missing),
      unit="books",
    )
  prices, regimes, preds = _load_market(session)
  for index, horizon in enumerate(missing, start=1):
    if on_progress is not None:
      on_progress(
        "paper",
        status="running",
        action="Simulating book",
        item=f"{horizon_label(horizon)} · $100k",
        detail=f"Marking the {horizon_label(horizon)} paper book",
        done=index - 1,
        total=len(missing),
        unit="books",
        horizon=horizon,
      )
    result = _simulate(prices, regimes, preds, horizon)
    if result and result["nav"]:
      _persist(session, horizon, result)
  session.commit()
  if on_progress is not None:
    on_progress(
      "paper",
      status="running",
      action="Paper books saved",
      item=f"{len(missing)} books",
      detail=f"Persisted {len(missing)} paper books",
      done=len(missing),
      total=len(missing),
      unit="books",
    )
  return get_paper(session, build=False)


def get_paper(session: Session, *, build: bool = True) -> dict:
  _ensure_schema()
  if session.query(PaperAccount).count() == 0:
    if not build:
      return {
        "starting_cash": STARTING_CASH,
        "cost_bps": COST_BPS,
        "gold_budget": GOLD_BUDGET,
        "note": NOTE,
        "horizons": list(HORIZONS),
        "horizon_labels": {str(h): horizon_label(h) for h in HORIZONS},
        "accounts": [],
      }
    return run_paper_tests(session)

  accounts = []
  for account in session.query(PaperAccount).order_by(PaperAccount.horizon_days).all():
    nav_rows = (
      session.query(PaperNav)
      .filter(PaperNav.account_id == account.id)
      .order_by(PaperNav.date)
      .all()
    )
    if not nav_rows:
      continue
    positions = session.query(PaperPosition).filter(PaperPosition.account_id == account.id).all()
    orders = (
      session.query(PaperOrder)
      .filter(PaperOrder.account_id == account.id)
      .order_by(PaperOrder.date.desc(), PaperOrder.id.desc())
      .limit(40)
      .all()
    )
    stats = _stats(nav_rows)
    last_day = nav_rows[-1].date
    symbols = [position.symbol for position in positions]
    last_px: dict[str, float] = {}
    if symbols:
      price_rows = (
        session.query(MacroDaily)
        .filter(MacroDaily.symbol.in_(symbols), MacroDaily.date <= last_day)
        .order_by(MacroDaily.date)
        .all()
      )
      for row in price_rows:
        last_px[row.symbol] = float(row.close)
    held = []
    for position in positions:
      px = last_px.get(position.symbol)
      value = position.shares * px if px else None
      held.append({
        "symbol": position.symbol,
        "shares": round(position.shares, 4),
        "price": None if px is None else round(px, 4),
        "value": None if value is None else round(value, 2),
        "weight": None if value is None else round(value / stats["nav"], 4),
      })
    held.sort(key=lambda item: item["value"] or 0, reverse=True)
    step = max(1, len(nav_rows) // 180)
    curve = [
      {
        "date": row.date.isoformat(),
        "nav": round(row.nav, 2),
        "gold": round(row.benchmark_gold, 2),
        "spx": round(row.benchmark_spx, 2),
      }
      for row in nav_rows[::step]
    ]
    if nav_rows[-1] not in nav_rows[::step]:
      last = nav_rows[-1]
      curve.append({
        "date": last.date.isoformat(),
        "nav": round(last.nav, 2),
        "gold": round(last.benchmark_gold, 2),
        "spx": round(last.benchmark_spx, 2),
      })
    n_rebalances = (
      session.query(PaperOrder.date)
      .filter(PaperOrder.account_id == account.id)
      .distinct()
      .count()
    )
    accounts.append({
      "horizon_days": account.horizon_days,
      "horizon_label": horizon_label(account.horizon_days),
      "starting_cash": account.starting_cash,
      "cost_bps": account.cost_bps,
      "inception": account.inception.isoformat(),
      "n_rebalances": n_rebalances,
      "positions": held,
      "orders": [
        {
          "date": order.date.isoformat(),
          "symbol": order.symbol,
          "side": order.side,
          "shares": round(order.shares, 4),
          "price": round(order.price, 4),
          "dollars": round(order.dollars, 2),
          "fee": round(order.fee, 2),
        }
        for order in orders
      ],
      "curve": curve,
      **stats,
    })
  return {
    "starting_cash": STARTING_CASH,
    "cost_bps": COST_BPS,
    "gold_budget": GOLD_BUDGET,
    "note": NOTE,
    "horizons": list(HORIZONS),
    "horizon_labels": {str(h): horizon_label(h) for h in HORIZONS},
    "accounts": accounts,
  }
