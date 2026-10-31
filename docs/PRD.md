# Product Requirements Document  
## Precious Metals Macro Intelligence Platform (PMIP)

| Field | Value |
| --- | --- |
| Product name | Precious Metals Macro Intelligence Platform (PMIP) |
| Product type | Metals allocation research desk (decision support) |
| Document status | Current product — v1 research desk |
| Primary framing | Not a trading system; does not place orders |
| Related docs | [README](../README.md), [Research note](research-note.md), [Executive guide](executive-platform-guide.md), [Numbers at a glance](numbers-at-a-glance.md) |

---

## 1. Overview

PMIP is a local-first research terminal for precious-metals allocation. It turns market prices, rates, and regime context into answers for two decisions a gold book actually faces:

1. **Gold budget** — Over the next few weeks, should gold exposure be larger or smaller versus equities and the rest of a multi-asset book?  
2. **Gold sleeve** — Given that budget, how should it be split between bullion, miners, and royalties?

The product is a **morning briefing and evidence desk**: stance, ranked names, playbook recipes, purged validation, and multi-horizon shadow books. It is not an OMS, broker, or live AUM product.

### Positioning one-liners

| Audience | Frame |
| --- | --- |
| Portfolio / interview | Macro intelligence desk for gold: regime, budget stance, sleeve signals, purged validation, multi-horizon paper books. |
| Quant / research PM | Research OS for gold-vs-markets and miners-vs-gold, with claim inventory, as-of scoring, and explicit costs. |
| Product / IC | Morning briefing for gold and mining exposure. Research suggestions only; no order routing. |

---

## 2. Problem

Metals desks and research users need a single place that:

- Separates **budget** (how much gold) from **sleeve** (which gold names).
- Shows **why** a view exists (drivers, regime, method notes).
- Distinguishes **live desk scores** from **citeable validation** (purged walk-forward, costs).
- Lets them run **shadow books** across horizons without claiming live alpha.

Without that, dashboards either overclaim “AI picks” or bury methodology so numbers cannot be defended in an interview or IC memo.

---

## 3. Goals and non-goals

### Goals
- Deliver a usable research desk for the two gold decisions above.
- Make every major number claim-aware (what it is allowed to mean).
- Support selective pipeline runs so users are not forced into multi-hour full rebuilds.
- Provide purged research output and paper books as the economic evidence layer.
- Stay runnable on a laptop (SQLite default) with optional Postgres/MLflow.

### Non-goals (v1)
- Order placement, broker connectivity, or compliance-approved advice.
- Guaranteed outperformance or a sold live track record.
- Full institutional market-data stack (Bloomberg/Refinitiv) as a requirement.
- Real-time intraday trading signals.

---

## 4. Users and jobs to be done

| Persona | Job |
| --- | --- |
| Quant / DS candidate (primary) | Demonstrate a defensible metals research stack in a portfolio. |
| Metals / macro analyst | Morning stance: budget, sleeve, regime, and what changed. |
| Research reviewer / PM | Ask “was this purged?” and “what does this number mean?” |
| Future design partner (later) | Consume a briefing process, not a black-box tip. |

---

## 5. Product principles

1. **Two decisions first** — Budget and sleeve are never collapsed into one “buy gold” score.  
2. **Claims over screenshots** — Method notes and claim inventory beat unexplained badges.  
3. **Live vs evidence** — Full-sample desk models for today’s signal; as-of / purged paths for history and paper.  
4. **Honest data labels** — Seeds and proxies are named as such.  
5. **Research language** — “Suggested playbook,” not “trade this now.”

---

## 6. Scope — current product (must ship / shipped)

### 6.1 Workspaces

| Code | Workspace | Requirement |
| --- | --- | --- |
| CMD | Command Center | Morning briefing: gold stance summary, regime, top signals, macro strip. |
| STR | Strategy Desk | Ranked playbooks from allocation, signals, regime, paper; recipe + evidence + caveats. |
| ALC | Gold vs Markets | Keep / Add / Reduce gold budget vs stocks/oil/copper with reasons. |
| MTL | Metals Book | Priced universe, tiers, gaps for unpriced instruments. |
| SIG | Signal Book | Per-name forecasts by horizon: P(beat gold), alpha, signal label; export. |
| MDL | Model Validation | Purged evidence table first; operational model catalog second. |
| PAP | Paper Books | Separate $100k books per horizon; NAV vs gold and SPX; method note. |
| PTF | Portfolio | HRP research weights and concentration analytics. |
| RSH | Research Desk | Regime history, hypotheses, macro series. |
| HST | Historical Outlook | As-of probability paths for key names. |
| XPL | How It Works | Explainability, data sources, method walkthrough. |
| RSK | Risk Monitor | GPR proxy, ETF flows, CB seed summary, agent scores. |

### 6.2 Forecast horizons

| Label | Trading days | Use |
| --- | ---: | --- |
| 5d | 5 | Short signal / paper clock |
| 10d | 10 | Default sleeve / research horizon |
| 1m | 20 | ~1 month |
| 3m | 63 | ~3 months |
| 6m | 126 | ~6 months |

### 6.3 Core decision rules (product contracts)

**Gold budget stance (ALC / paper)**  
- Inputs: gold vs equity expected spread, real yield, dollar trend, regime gold bias.  
- Output: Add → 60% gold sleeve budget; Keep → 30%; Reduce → 10%; residual to SPX.

**Signal labels (SIG)**  
| Label | Rule |
| --- | --- |
| Long | P(beat gold) ≥ 60% and expected alpha > 0 |
| Overweight | P(beat gold) ≥ 55% |
| Neutral | Between 45% and 55% |
| Underweight | P(beat gold) ≤ 45% |
| Short | P(beat gold) ≤ 40% and expected alpha < 0 |

**Sleeve construction (paper / Strategy Desk)**  
- Equal-weight up to 8 names labeled long or overweight; fallback GLD (or GC=F).  
- Strategy Desk composes recipes from the same budgets and sleeve rules.

**Expected alpha**  
- Model expected return minus a flat 1 percentage-point hurdle (ranking tool, not profit after costs).

**P(beat GDX)**  
- Displayed as 95% × P(beat gold) — shortcut, not a second model.

### 6.4 Evidence layer

| Capability | Requirement |
| --- | --- |
| Purged research | `make research`: embargo = horizon, non-overlapping folds, 10 bp flip cost, baselines (always-hold, momentum, logistic). Cite via docs/research. |
| As-of scoring | History and paper use models refit with horizon embargo at each score date (`asof_h*`). |
| Live scoring | Latest desk signals may use full-sample registry models; UI/docs must not equate them to paper. |
| Claim inventory | Research note documents allowed meanings for key on-screen figures. |

### 6.5 Pipeline and ops

| Capability | Requirement |
| --- | --- |
| Run picker | Presets: refresh prices, rescore signals, train short horizons, rebuild paper, full; custom stages/horizons/universe/walk-forward. |
| Progress tracker | Stage list, percent, current work item, activity log; minimize/expand. |
| Sync | Reload saved warehouse state without re-running ETL/train. |
| Default store | SQLite; optional Postgres + MLflow. |

### 6.6 Data requirements (v1 honesty)

| Series | Source | Product requirement |
| --- | --- | --- |
| Prices (futures, ETFs, equities, SPX, VIX, oil) | Yahoo Finance | Daily closes in warehouse |
| Yields / real yields | FRED when keyed; else Yahoo + estimate | Document fallback in UI/docs |
| ETF flows | Derived proxy | Labeled as estimate |
| CB gold / miner fundamentals | Seed | Labeled illustrative / seed |
| Geopolitical risk | Proxy | Not presented as live news NLP |

---

## 7. Functional requirements (summary)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-1 | User can view Keep/Add/Reduce gold budget with drivers. | P0 |
| FR-2 | User can browse signal book by horizon with labels and export. | P0 |
| FR-3 | User can view ranked Strategy Desk playbooks with recipes and caveats. | P0 |
| FR-4 | User can run selective or full pipeline and monitor progress (including minimize). | P0 |
| FR-5 | User can view multi-horizon paper books vs gold and SPX. | P0 |
| FR-6 | User can view purged research evidence on Model Validation. | P0 |
| FR-7 | User can view as-of historical outlook charts. | P0 |
| FR-8 | User can inspect metals universe and unpriced gaps. | P1 |
| FR-9 | User can view regime, knowledge-graph hypotheses, and risk proxies. | P1 |
| FR-10 | System regenerates purged research via `make research`. | P0 |
| FR-11 | API exposes dashboard, allocation, strategies, research, paper, history, pipeline options/run/status. | P0 |

---

## 8. Non-functional requirements

| Area | Requirement |
| --- | --- |
| Performance | Short presets usable in minutes; full run may take 1–3+ hours — communicated in UI. |
| Reliability | Pipeline failures surface in tracker/toast; status pollable. |
| Explainability | Method notes on major workspaces; claim inventory for citeable numbers. |
| Portability | Runs locally with Python 3.11+, Node 20+, `make install` / `make dev`. |
| Security (v1) | Local single-user; no multi-tenant auth required. |
| Compliance posture | Copy stays research/decision-support; not investment advice. |

---

## 9. Success metrics

### Portfolio / interview success
- Can explain the two decisions and live-vs-as-of split in under two minutes.
- Can point to purged table + paper book as evidence, not only signal badges.
- README and PRD match the running product.

### Product quality (internal)
- Pipeline presets reduce time-to-refresh for common jobs vs always-full.
- Paper books rebuild from as-of scores after history stage.
- Strategy Desk primary playbook always includes budget, sleeve, residual, evidence, caveat.

### Explicitly not success metrics (v1)
- Live Sharpe, client AUM, or subscription revenue.

---

## 10. Out of scope / known limits

- Short historical sample relative to institutional backtests.
- Seeded CB gold and miner fundamentals.
- GPR as proxy only.
- Dual scoring paths (full-sample live vs as-of paper) must stay labeled.
- No broker, auth, SLA, or licensed data contracts in v1.
- Geared ETFs may be priced but not modeled as primary targets.

---

## 11. Roadmap (product phases)

Aligned with the desk maturity path:

| Phase | Outcome |
| --- | --- |
| **A — Portfolio ready (now)** | Two decisions, purged evidence, as-of paper, Strategy Desk, claim-aware UI, README/PRD. |
| **B — Boutique research desk** | FRED required in “production” mode; quarantine or replace seeds; constraints/risk on books; version stamps on signals. |
| **C — Shadow service** | Auth, scheduled runs, exportable IC brief, design-partner weekly use. |
| **D — Sellable briefing** | Licensed data, support/SLA, legal review — only after C proves process value. |

---

## 12. Acceptance criteria (v1 desk)

The product meets this PRD when:

1. All listed workspaces load from the API after a successful pipeline (or show empty states with a clear next action / Run pipeline CTA). ✅  
2. Gold budget and sleeve rules match §6.3 in allocation, paper, and Strategy Desk. ✅  
3. Horizons include 5d through 6m where models exist. ✅  
4. Model Validation surfaces purged evidence when `docs/research/results.json` exists. ✅  
5. Paper books use as-of scores only; live signal book may use full-sample models — UI badges Path/live/as-of. ✅  
6. Pipeline picker supports at least the documented presets; tracker can be minimized. ✅  
7. README and this PRD describe the same product framing and limits. ✅  

Phase B items (required FRED gate, seed quarantine, model-only paper path) remain deferred — see §11 / §13.

---

## 13. Open decisions (deferred)

- Model-only paper book beside the policy (yield/dollar/regime) book for cleaner interviews.  
- Narrow scored universe permanently to liquid sleeve for all live training.  
- Required FRED key gate for “production” mode.  
- External packaging name (PMIP vs “Metals Desk” / similar) for go-to-market later.

---

## Document control

| Version | Date | Notes |
| --- | --- | --- |
| 1.0 | 2026-10-30 | Initial PRD reflecting shipped research desk |
