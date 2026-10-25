"""Listed metals book: what is priced, what is modeled, and what the feed cannot mark."""

from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from pmip.constants import METALS_INSTRUMENTS, METALS_PRICED, METALS_UNPRICED
from pmip.db.models import MacroDaily, ModelPrediction


def get_universe(session: Session) -> dict:
  symbols = [item.symbol for item in METALS_PRICED]
  rows = (
    session.query(MacroDaily)
    .filter(MacroDaily.symbol.in_(symbols))
    .order_by(MacroDaily.date)
    .all()
  )
  frame = pd.DataFrame([{"date": r.date, "symbol": r.symbol, "close": float(r.close)} for r in rows])
  latest: dict[str, dict] = {}
  if not frame.empty:
    for symbol, group in frame.groupby("symbol"):
      group = group.sort_values("date")
      last = group.iloc[-1]
      prev = group.iloc[-21] if len(group) > 21 else None
      change = None
      if prev is not None and prev["close"]:
        change = float(last["close"] / prev["close"] - 1)
      latest[symbol] = {
        "price": round(float(last["close"]), 4),
        "as_of": last["date"].isoformat(),
        "change_20d": None if change is None else round(change, 4),
      }

  modeled = {
    row[0]
    for row in session.query(ModelPrediction.entity).distinct().all()
  }

  priced = []
  for item in METALS_PRICED:
    mark = latest.get(item.symbol)
    priced.append({
      "symbol": item.symbol,
      "name": item.name,
      "metal": item.metal,
      "instrument": item.instrument,
      "tier": item.tier,
      "scored": item.scored,
      "modeled": item.symbol in modeled,
      "price": None if mark is None else mark["price"],
      "as_of": None if mark is None else mark["as_of"],
      "change_20d": None if mark is None else mark["change_20d"],
      "note": item.note,
    })

  unpriced = [
    {
      "symbol": item.symbol,
      "name": item.name,
      "metal": item.metal,
      "instrument": item.instrument,
      "note": item.note,
    }
    for item in METALS_UNPRICED
  ]

  def _count(items, key):
    out: dict[str, int] = {}
    for item in items:
      out[item[key]] = out.get(item[key], 0) + 1
    return out

  with_price = sum(1 for row in priced if row["price"] is not None)
  return {
    "priced": priced,
    "unpriced": unpriced,
    "summary": {
      "listed": len(METALS_INSTRUMENTS),
      "on_feed": len(priced),
      "with_price": with_price,
      "awaiting_price": len(priced) - with_price,
      "modeled": sum(1 for row in priced if row["modeled"]),
      "scored_next_run": sum(1 for row in priced if row["scored"]),
      "not_on_feed": len(unpriced),
      "by_metal": _count(priced, "metal"),
      "by_instrument": _count(priced, "instrument"),
    },
  }
