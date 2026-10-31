"""Strategy Desk — ranked playbooks from live warehouse data.

Composes allocation stance, signal-book longs, regime bias, and paper-book
results into explicit recipes. Rule-based scores only; no new model fit.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from pmip.api.allocation_service import get_allocation
from pmip.api.paper_service import GOLD_BUDGET, TOP_N, get_paper
from pmip.api.research_service import get_signal_book, load_purged_evidence
from pmip.constants import horizon_label
from pmip.models.regime import get_current_regime
from pmip.research.knowledge_graph import REGIME_HYPOTHESES

SLEEVE_HORIZON = 10
CAVEAT = (
  "Research suggestion composed from current warehouse signals. "
  "Not investment advice and not an order ticket."
)


def _sleeve_from_signals(signals: list[dict]) -> list[dict]:
  ranked = []
  for row in signals:
    if row.get("entity") in ("SPX", "GC=F"):
      continue
    if row.get("signal") not in ("long", "overweight"):
      continue
    ranked.append(row)
  ranked.sort(key=lambda r: float(r.get("expected_alpha") or 0.0), reverse=True)
  chosen = ranked[:TOP_N]
  if not chosen:
    return [{"entity": "GLD", "label": "SPDR Gold Shares", "weight": 1.0, "signal": "fallback"}]
  weight = 1.0 / len(chosen)
  return [
    {
      "entity": row["entity"],
      "label": row.get("label") or row["entity"],
      "weight": round(weight, 4),
      "signal": row.get("signal"),
      "prob_outperform_gold": row.get("prob_outperform_gold"),
      "expected_alpha": row.get("expected_alpha"),
    }
    for row in chosen
  ]


def _paper_rank(accounts: list[dict]) -> dict | None:
  if not accounts:
    return None
  best = None
  best_score = None
  for account in accounts:
    ret = float(account.get("total_return") or 0.0)
    dd = abs(float(account.get("max_drawdown") or 0.0))
    score = ret - 0.5 * dd
    if best_score is None or score > best_score:
      best_score = score
      best = {**account, "risk_adj_score": round(score, 4)}
  return best


def _tag_for_stance(stance: str) -> str:
  if stance == "add":
    return "constructive"
  if stance == "reduce":
    return "defensive"
  return "neutral"


def _confidence(base: float, *, regime_bias: str, stance: str, n_sleeve: int, paper_ok: bool) -> float:
  score = base
  if regime_bias == "bullish" and stance == "add":
    score += 0.12
  if regime_bias == "bearish" and stance == "reduce":
    score += 0.12
  if regime_bias == "bullish" and stance == "reduce":
    score -= 0.08
  if regime_bias == "bearish" and stance == "add":
    score -= 0.08
  if n_sleeve >= 4:
    score += 0.05
  if paper_ok:
    score += 0.08
  return round(min(max(score, 0.15), 0.92), 2)


def get_strategies(session: Session) -> dict:
  allocation = get_allocation(session)
  signals = get_signal_book(session, horizon=SLEEVE_HORIZON)
  paper = get_paper(session, build=False)
  accounts = paper.get("accounts") or []
  best_paper = _paper_rank(accounts)
  evidence = load_purged_evidence()

  regime = get_current_regime(session)
  regime_match = None
  if regime:
    regime_match = next((r for r in REGIME_HYPOTHESES if r.regime_id == regime.get("regime_id")), None)
  gold_bias = regime_match.gold_bias if regime_match else "neutral"
  regime_name = regime.get("regime_name") if regime else None

  stance = allocation.get("stance") or "keep"
  gold_budget = GOLD_BUDGET.get(stance, GOLD_BUDGET["keep"])
  sleeve = _sleeve_from_signals(signals)
  residual = round(1.0 - gold_budget, 4)
  paper_ok = best_paper is not None and best_paper.get("n_rebalances", 0) >= 2

  strategies: list[dict] = []

  # 1) Gold budget playbook
  strategies.append({
    "id": "gold_budget",
    "title": "Gold budget",
    "tag": _tag_for_stance(stance),
    "action": {
      "add": f"Raise the gold sleeve to {int(gold_budget * 100)}% of the book.",
      "keep": f"Hold the gold sleeve near {int(gold_budget * 100)}% of the book.",
      "reduce": f"Cut the gold sleeve to {int(gold_budget * 100)}% of the book.",
    }[stance],
    "confidence": _confidence(0.55, regime_bias=gold_bias, stance=stance, n_sleeve=len(sleeve), paper_ok=paper_ok),
    "horizon_days": SLEEVE_HORIZON,
    "horizon_label": horizon_label(SLEEVE_HORIZON),
    "gold_budget": gold_budget,
    "sleeve": sleeve,
    "residual": {"symbol": "SPX", "weight": residual, "label": "S&P 500"},
    "evidence": list(allocation.get("reasons") or [])[:4],
    "caveats": [CAVEAT, allocation.get("note") or ""],
    "score": 70 + (15 if stance == "add" else 0) + (-10 if stance == "reduce" else 0),
  })

  # 2) Miner sleeve playbook
  sleeve_names = ", ".join(item["entity"] for item in sleeve[:5])
  if len(sleeve) > 5:
    sleeve_names += f" +{len(sleeve) - 5}"
  strategies.append({
    "id": "miner_sleeve",
    "title": "Miner / bullion sleeve",
    "tag": "constructive" if any(s.get("signal") == "long" for s in sleeve) else "neutral",
    "action": (
      f"Equal-weight the gold budget across {len(sleeve)} names: {sleeve_names}."
      if sleeve[0].get("signal") != "fallback"
      else "No long/overweight names cleared the cut — park the gold budget in GLD."
    ),
    "confidence": _confidence(
      0.5 if sleeve[0].get("signal") != "fallback" else 0.35,
      regime_bias=gold_bias,
      stance=stance,
      n_sleeve=0 if sleeve[0].get("signal") == "fallback" else len(sleeve),
      paper_ok=paper_ok,
    ),
    "horizon_days": SLEEVE_HORIZON,
    "horizon_label": horizon_label(SLEEVE_HORIZON),
    "gold_budget": gold_budget,
    "sleeve": sleeve,
    "residual": {"symbol": "SPX", "weight": residual, "label": "S&P 500"},
    "evidence": [
      f"Signal book horizon {horizon_label(SLEEVE_HORIZON)} · {sum(1 for s in signals if s.get('signal') in ('long', 'overweight'))} long/OW names.",
      f"Top sleeve weight {sleeve[0]['entity']} ({sleeve[0].get('signal')}).",
    ],
    "caveats": [CAVEAT, "Sleeve picks come from the live signal book, not the purged research table."],
    "score": 60 + min(len(sleeve), 8) * 3,
  })

  # 3) Horizon pick from paper
  if best_paper:
    h = int(best_paper["horizon_days"])
    strategies.append({
      "id": "horizon_pick",
      "title": f"Preferred rebalance clock · {horizon_label(h)}",
      "tag": "constructive" if float(best_paper.get("total_return") or 0) >= 0 else "defensive",
      "action": (
        f"Prefer the {horizon_label(h)} paper clock: "
        f"{float(best_paper.get('total_return') or 0) * 100:+.1f}% total return, "
        f"max drawdown {float(best_paper.get('max_drawdown') or 0) * 100:.1f}%."
      ),
      "confidence": _confidence(0.48, regime_bias=gold_bias, stance=stance, n_sleeve=len(sleeve), paper_ok=True),
      "horizon_days": h,
      "horizon_label": horizon_label(h),
      "gold_budget": gold_budget,
      "sleeve": sleeve,
      "residual": {"symbol": "SPX", "weight": residual, "label": "S&P 500"},
      "evidence": [
        f"Best risk-adjusted paper book among {len(accounts)} horizons.",
        f"Inception {best_paper.get('inception')} · {best_paper.get('n_rebalances')} rebalances.",
        f"Vs gold {float(best_paper.get('benchmark_gold_return') or 0) * 100:+.1f}%, "
        f"vs SPX {float(best_paper.get('benchmark_spx_return') or 0) * 100:+.1f}%.",
      ],
      "caveats": [
        CAVEAT,
        "Paper paths use purged as-of scores with 10 bps costs; still a short-sample illustration.",
      ],
      "score": 55 + int(100 * float(best_paper.get("risk_adj_score") or 0)),
    })
  else:
    strategies.append({
      "id": "horizon_pick",
      "title": "Preferred rebalance clock · 10d",
      "tag": "neutral",
      "action": "Paper books are empty — default to the 10-day clock until as-of history is rebuilt.",
      "confidence": 0.3,
      "horizon_days": SLEEVE_HORIZON,
      "horizon_label": horizon_label(SLEEVE_HORIZON),
      "gold_budget": gold_budget,
      "sleeve": sleeve,
      "residual": {"symbol": "SPX", "weight": residual, "label": "S&P 500"},
      "evidence": ["Run the paper / history pipeline stages to unlock horizon ranking."],
      "caveats": [CAVEAT],
      "score": 25,
    })

  # 4) Regime overlay
  strategies.append({
    "id": "regime_overlay",
    "title": "Regime overlay",
    "tag": "constructive" if gold_bias == "bullish" else ("defensive" if gold_bias == "bearish" else "neutral"),
    "action": (
      f"Environment is {regime_name or 'unknown'}; standing research view on gold is {gold_bias}."
    ),
    "confidence": _confidence(0.42, regime_bias=gold_bias, stance=stance, n_sleeve=len(sleeve), paper_ok=paper_ok),
    "horizon_days": SLEEVE_HORIZON,
    "horizon_label": horizon_label(SLEEVE_HORIZON),
    "gold_budget": gold_budget,
    "sleeve": sleeve,
    "residual": {"symbol": "SPX", "weight": residual, "label": "S&P 500"},
    "evidence": [
      f"Regime confidence {float((regime or {}).get('confidence') or 0) * 100:.0f}%." if regime else "No regime row yet.",
      f"Allocation stance is {stance}; overlay {'aligns' if (gold_bias == 'bullish' and stance == 'add') or (gold_bias == 'bearish' and stance == 'reduce') else 'is mixed'} with the budget call.",
    ],
    "caveats": [
      CAVEAT,
      "Regime gold bias is a fixed standing hypothesis for the state, not a live PnL backtest.",
    ],
    "score": 45 + (10 if gold_bias == "bullish" else 0) + (5 if gold_bias == "bearish" else 0),
  })

  # 5) Defensive when reduce or headwinds
  if stance == "reduce" or allocation.get("yield_role") == "headwind" or allocation.get("dollar_role") == "headwind":
    def_budget = GOLD_BUDGET["reduce"]
    strategies.append({
      "id": "defensive",
      "title": "Defensive residual",
      "tag": "defensive",
      "action": (
        f"Keep only {int(def_budget * 100)}% in the gold sleeve and "
        f"{int((1 - def_budget) * 100)}% in SPX until yields/dollar ease."
      ),
      "confidence": _confidence(0.58, regime_bias=gold_bias, stance="reduce", n_sleeve=len(sleeve), paper_ok=paper_ok),
      "horizon_days": SLEEVE_HORIZON,
      "horizon_label": horizon_label(SLEEVE_HORIZON),
      "gold_budget": def_budget,
      "sleeve": sleeve[:3] if sleeve[0].get("signal") != "fallback" else sleeve,
      "residual": {"symbol": "SPX", "weight": round(1 - def_budget, 4), "label": "S&P 500"},
      "evidence": [
        f"Yield role: {allocation.get('yield_role')}.",
        f"Dollar role: {allocation.get('dollar_role')}.",
        f"Stance: {stance}.",
      ],
      "caveats": [CAVEAT],
      "score": 65 if stance == "reduce" else 50,
    })

  if evidence and evidence.get("studies"):
    cite = evidence["studies"][0]
    for item in strategies:
      item["evidence"] = list(item.get("evidence") or [])
      item["evidence"].append(
        f"Cite purged study '{cite.get('name')}': HGB AUC "
        f"{cite.get('auc') if cite.get('auc') is not None else '—'} on {cite.get('n_oos')} OOS dates."
      )

  strategies.sort(key=lambda s: float(s.get("score") or 0), reverse=True)
  # Normalize scores to a 0-100 display range after sort
  if strategies:
    top = max(float(s["score"]) for s in strategies) or 1.0
    for item in strategies:
      item["score"] = round(100.0 * float(item["score"]) / top, 1)

  primary = strategies[0]["id"] if strategies else None

  return {
    "as_of": allocation.get("as_of"),
    "primary": primary,
    "note": (
      "Playbooks reuse the same Keep/Add/Reduce budgets and long/OW sleeve rules as the paper books. "
      "The miner sleeve is taken from the live full-sample signal book; horizon ranking and "
      "paper evidence use purged as-of scores. Composed from today's warehouse — not a separate optimizer."
    ),
    "drivers": {
      "stance": stance,
      "gold_budget": gold_budget,
      "regime_name": regime_name,
      "gold_bias": gold_bias,
      "sleeve_horizon_days": SLEEVE_HORIZON,
      "n_long_signals": sum(1 for s in signals if s.get("signal") in ("long", "overweight")),
      "best_paper_horizon": best_paper.get("horizon_days") if best_paper else None,
      "best_paper_return": best_paper.get("total_return") if best_paper else None,
      "yield_role": allocation.get("yield_role"),
      "dollar_role": allocation.get("dollar_role"),
    },
    "strategies": strategies,
  }
