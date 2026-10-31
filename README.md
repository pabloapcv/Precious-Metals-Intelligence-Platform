# Precious Metals Macro Intelligence Platform (PMIP)

**A metals allocation research desk** — not a trading platform and not “AI for gold.”

It answers two questions a gold book actually faces:

1. **Gold budget.** Over the next few weeks, should exposure to gold be larger or smaller versus equities (and the rest of a multi-asset book)?
2. **Gold sleeve.** Given that budget, how should it be split between bullion and miners / royalties?

The screen is a decision desk. The evidence behind it is a purged walk-forward study with embargo, baselines, and turnover costs. Several on-screen figures are explicit rules rather than measured probabilities; the [claim inventory](docs/research-note.md) says which is which. Full product requirements: [docs/PRD.md](docs/PRD.md).

---

## How to frame it

| Audience | One-liner |
| --- | --- |
| Portfolio / interview | Precious-metals macro intelligence desk: regime detection, gold-budget and miner-sleeve signals, purged validation, and multi-horizon paper books. |
| Quant / research PM | Research OS for two decisions — gold vs markets, and miners vs gold — with claim inventory, as-of scoring, and explicit costs. |
| Product | A morning briefing for gold and mining exposure: stance, sleeve, evidence, and simulated books. It does not place trades. |

**What it is not:** an OMS/broker, live AUM product, or a claim of guaranteed alpha. Market data is mostly free Yahoo closes plus optional FRED; some tables are still seeded.

---

## What the desk does

### Decisions
- **Keep / Add / Reduce** gold versus stocks, cash, oil, and copper ([Gold vs Markets](docs/executive-platform-guide.md)).
- **Signal book** — for each scored name and horizon, P(beat gold), expected return / alpha, and a long–short label.
- **Strategy Desk** — ranked playbooks composed from stance, sleeve, regime, and paper results (research suggestions with explicit recipes and caveats).

### Evidence
- **Purged research** (`make research`) — citeable gold-vs-SPX and GDX-vs-gold studies: embargo = horizon, non-overlapping periods, 10 bp flip cost, baselines (always-hold, momentum, logistic).
- **Model catalog** — operational walk-forward diagnostics for deployed entity × horizon models.
- **Paper books** — separate $100k accounts for **5d · 10d · 1m · 3m · 6m** that rebalance on their own clocks using **purged as-of** forecasts (horizon embargo), mark to market vs gold and SPX.

### Context
- Four-state **HMM regime**, standing gold/miner biases, causal **knowledge graph**.
- Macro strip: dollar, real yields, VIX, oil, copper, ETF-flow proxies, CB seed rows.

### Ops
- **Pipeline run picker** — short jobs (refresh prices, rescore signals, train short horizons, rebuild paper) or full run.
- Granular progress tracker (stage, current item, activity log).

---

## Architecture

```
React terminal (workspaces)
        │
     FastAPI
        │
 ┌──────┼──────────────────────────────┐
 │      │                              │
 Signals / Strategy / Allocation    Research note
 Paper / History / Portfolio        (purged WF)
        │                              │
 Models (LightGBM or sklearn HGB)  ←──┘
 Regime HMM · Feature store
        │
 SQLite warehouse (default)  or  Postgres
        │
 ETL: Yahoo Finance · FRED (optional) · derived flows · seeds
```

Default store is local SQLite (`data/pmip.db`). Postgres + MLflow are optional via Docker.

---

## Workspaces

| Code | Workspace | Role |
| --- | --- | --- |
| CMD | Command Center | Morning briefing |
| STR | Strategy Desk | Ranked playbooks from live data |
| ALC | Gold vs Markets | Keep / Add / Reduce gold budget |
| MTL | Metals Book | Priced universe and gaps |
| SIG | Signal Book | Per-name forecasts by horizon |
| MDL | Model Validation | Purged evidence + model catalog |
| PAP | Paper Books | Multi-horizon shadow PnL |
| PTF | Portfolio | HRP research weights |
| RSH | Research Desk | Regime history, hypotheses, macro |
| HST | Historical Outlook | As-of probability paths |
| XPL | How It Works | Method and claim notes |
| RSK | Risk Monitor | GPR proxy, flows, CB, agents |

---

## Horizons

Forecast and paper clocks (trading days):

| Label | Days | Approx. |
| --- | ---: | --- |
| 5d | 5 | ~1 week |
| 10d | 10 | ~2 weeks |
| 1m | 20 | ~1 month |
| 3m | 63 | ~3 months |
| 6m | 126 | ~6 months |

Live desk signals use full-sample registry models. **History charts and paper books** use **as-of** refits with a horizon embargo so labels that would reach into the score date are excluded.

---

## Data sources

| Data | Source | Notes |
| --- | --- | --- |
| Futures, ETFs, equities, SPX, VIX, oil | Yahoo Finance | Daily closes in the warehouse |
| Treasury / real yields / breakevens | FRED | When `FRED_API_KEY` is set; otherwise Yahoo yields and a real-yield estimate |
| ETF flows (GLD, IAU) | Derived from Yahoo | Proxy, not official flow files |
| Central-bank gold | Seed rows | Illustrative WGC-style monthly |
| Geopolitical risk | Proxy | VIX / oil vol composite (GDELT-ready hooks) |
| Miner fundamentals | Seed quarterly | AISC / production placeholders |

Unpriced gaps (LME base metals, lease rates, physical premiums, options) are listed in the Metals Book.

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+
- (Optional) [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html)
- (Optional) Docker for Postgres + MLflow

### Setup

```bash
cp .env.example .env          # optional: FRED_API_KEY, DATABASE_URL

make install                  # Python venv + frontend deps
make init-db                  # SQLite warehouse
make pipeline                 # or use Run Pipeline in the UI with a short preset
make dev                      # build frontend + API on http://localhost:8000
```

Open **http://localhost:8000**. API docs: **http://localhost:8000/docs**.

```bash
make research                 # regenerate purged tables → docs/research/
make test
make verify
```

### Pipeline presets (UI)

| Preset | Typical use |
| --- | --- |
| Refresh prices | ETL + features + regime |
| Rescore signals | Predict + portfolio from existing models |
| Train short horizons | Liquid sleeve · 5d / 10d / 1m |
| Rebuild paper books | As-of history + paper |
| Full pipeline | Everything (long) |

Customize stages, horizons, liquid vs full universe, and walk-forward on/off.

### Optional Postgres + MLflow

```bash
make up
# DATABASE_URL=postgresql://pmip:pmip_dev@localhost:5432/precious_metals
make init-db && make pipeline
```

---

## Research & validation

The number to cite for “does the model help?” is the purged study, not the operational catalog alone.

```bash
make research
```

That rewrites [docs/research-note.md](docs/research-note.md), [docs/research/latest-results.md](docs/research/latest-results.md), and `docs/research/results.json`.

Method in short:

- Label on day *t*: does the entity beat the benchmark over the next *h* days?
- Training rows whose labels reach into the test day are removed (**embargo = h**).
- Folds step by *h* so economic periods do not overlap.
- Wealth compounds those non-overlapping returns minus **10 bps** when the book flips.
- Baselines: always entity, always benchmark, 20-day relative momentum, small logistic.

Also see [docs/executive-platform-guide.md](docs/executive-platform-guide.md) and [docs/numbers-at-a-glance.md](docs/numbers-at-a-glance.md).

---

## API (selected)

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/dashboard` | Morning briefing |
| `GET /api/v1/allocation` | Keep / Add / Reduce gold budget |
| `GET /api/v1/strategies` | Ranked Strategy Desk playbooks |
| `GET /api/v1/research` | Signals, catalog, regime, portfolio analytics |
| `GET /api/v1/paper` | Multi-horizon paper books |
| `GET /api/v1/history` | As-of outlook series |
| `GET /api/v1/universe` | Metals book |
| `GET /api/v1/pipeline/options` | Presets and knobs |
| `POST /api/v1/pipeline/run` | Start full or partial pipeline |
| `GET /api/v1/pipeline/status` | Progress snapshot |

---

## Layout

| Path | Role |
| --- | --- |
| `src/pmip/etl/` | Market and macro ingestion |
| `src/pmip/features/` | Feature store |
| `src/pmip/models/` | Training, as-of scoring, regime |
| `src/pmip/research/` | Purged evaluation, knowledge graph |
| `src/pmip/portfolio/` | HRP / research weights |
| `src/pmip/api/` | FastAPI services |
| `src/pmip/pipeline/` | Runner, progress, run options |
| `frontend/` | React terminal |
| `docs/` | Research note and guides |
| `scripts/` | CLI entrypoints |

---

## Limits (read before citing numbers)

- Sample length is still short relative to institutional backtests.
- Without FRED, real yields are estimated.
- Central-bank and miner-fundamental tables are **seeds**, not live vendor feeds.
- Live signal book / Strategy sleeve use **full-sample** registry models (UI badges `live`); paper / history use **as-of** scores (`as-of`). See [docs/numbers-at-a-glance.md](docs/numbers-at-a-glance.md).
- Paper books are shadow simulations (10 bps, liquid sleeve, rule-based stance) — not audited live track record.
- Geopolitical risk is a **proxy**, not a news NLP feed.

---

## Extending

- Wire real WGC / IMF CB gold and CapIQ or EDGAR fundamentals; quarantine seeds.
- Point-in-time fundamentals and licensed prices for diligence-ready runs.
- GDELT / ACLED into `etl/geopolitical.py`.
- Model-only paper book beside the policy (yield/dollar/regime) book for cleaner interviews.

---

## License

MIT
