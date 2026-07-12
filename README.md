# Precious Metals Macro Intelligence Platform (PMIP)

An institutional-grade quantitative research platform that predicts the probability of outperformance for gold, senior/mid/junior miners, and gold royalty companies — driven by macro regime detection, feature engineering, ML models, and AI research agents.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     React Dashboard (Phase 9)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │ FastAPI
┌────────────────────────────▼────────────────────────────────────┐
│  Predictions │ Regimes │ Portfolio │ Knowledge Graph │ Agents  │
└──────┬───────────────┬──────────────┬─────────────────────────┘
       │               │              │
┌──────▼──────┐ ┌──────▼──────┐ ┌────▼─────────────────────────┐
│ LightGBM    │ │ HMM Regime  │ │ HRP / Mean-Var / Kelly       │
│ Walk-Fwd    │ │ Detection   │ │ Portfolio Optimizer          │
└──────┬──────┘ └──────┬──────┘ └──────────────────────────────┘
       │               │
┌──────▼───────────────▼──────────────────────────────────────────┐
│                    Feature Store (Phase 4)                       │
│  Returns │ Volatility │ RSI/MACD │ Ratios │ Surprises          │
└──────┬──────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────┐
│              PostgreSQL Data Warehouse (Phase 2-3)               │
│  Macro │ ETF Flows │ Central Banks │ GPR │ Miner Fundamentals   │
└──────┬──────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────┐
│           Prefect ETL Pipeline (daily orchestration)             │
│  FRED │ yfinance │ WGC │ GDELT proxy │ SEC filings             │
└─────────────────────────────────────────────────────────────────┘
```

## Knowledge Graph (Phase 1)

The platform encodes testable macro hypotheses as a causal knowledge graph:

```
Fed Policy → Real Interest Rates → Dollar (DXY) → Gold → Mining Margins → Mining Stocks
```

Expanded with: China demand, central bank purchases, inflation, oil, treasury yields, volatility, wars, sanctions, and ETF flows. Every edge has a directional hypothesis with magnitude hints.

**Key hypothesis:** If real yields rise 40bp, GDX underperforms gold by 3-8%.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- (Optional) FRED API key from [FRED](https://fred.stlouisfed.org/docs/api/api_key.html)

### Setup

```bash
cp .env.example .env          # optional: add FRED_API_KEY for treasury/real yield data

# Install dependencies (once)
make install

# Initialize database (SQLite — no Docker required)
make init-db

# Run full pipeline (~2 min) — fetches market data, trains models, generates predictions
make pipeline

# Start API (terminal 1)
make api

# Start dashboard (terminal 2)
make frontend
```

Open **http://localhost:3000** for the dashboard (Vite may pick another port if 3000 is busy — check terminal output). API docs: **http://localhost:8000/docs**

Verify everything works:

```bash
make verify
```

### Optional: PostgreSQL + MLflow via Docker

```bash
make up                       # Start PostgreSQL + MLflow
# Set DATABASE_URL=postgresql://pmip:pmip_dev@localhost:5432/precious_metals in .env
make init-db && make pipeline
```

## Phases

| Phase | Module | Description |
|-------|--------|-------------|
| 1 | `research/knowledge_graph.py` | Causal hypotheses & regime definitions |
| 2 | `etl/` | Macro, ETF flows, central banks, geopolitical data |
| 3 | `etl/miners.py` | Quarterly fundamentals per company |
| 4 | `features/engineering.py` | Technical & cross-asset feature engineering |
| 5 | `models/regime.py` | HMM-based regime detection (4 regimes) |
| 6 | `models/training.py` | LightGBM with walk-forward validation |
| 7 | `portfolio/optimizer.py` | HRP, mean-variance, Kelly sizing |
| 8 | `agents/research.py` | Macro, Geopolitical, Mining, Quant agents |
| 9 | `api/main.py` + `frontend/` | FastAPI backend & React dashboard |

## Prediction Targets

| Asset Class | Proxy | Tier |
|-------------|-------|------|
| Gold | GLD / GC=F | gold |
| Senior miners | GDX, NEM, AEM, B | senior |
| Mid-tier | AGI, KGC | mid |
| Junior miners | GDXJ | junior |
| Royalties | RING | royalty |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/dashboard` | Morning intelligence briefing |
| `GET /api/v1/predictions` | Outperformance probabilities |
| `GET /api/v1/regime/current` | Current market regime |
| `GET /api/v1/knowledge-graph` | Full causal graph |
| `GET /api/v1/hypotheses/{target}` | Hypotheses affecting a variable |
| `POST /api/v1/pipeline/run` | Trigger full pipeline |
| `GET /api/v1/etf-flows` | Gold ETF flow data |
| `GET /api/v1/central-banks` | CB purchase data |

## Dashboard Output

Every morning the dashboard generates:

- **Macro:** Fed probability, dollar strength, real yields, inflation
- **Gold:** Bullish probability (e.g., 78%), 10-day horizon
- **Mining:** Ranked companies by expected alpha
- **Risk:** War probability, oil disruption, CB buying, ETF flows
- **Portfolio:** Top 10 miners with HRP-optimized weights
- **Agents:** Macro, geopolitical, mining, and quant agent scores

## Data Sources

| Data | Source | Frequency |
|------|--------|-----------|
| Gold, silver, copper, oil, VIX, SPX | yfinance / FRED | Daily |
| Treasury yields, real yields, breakevens | FRED | Daily |
| ETF flows (GLD, IAU) | yfinance (proxy) | Daily |
| Central bank purchases | WGC (seed data) | Monthly |
| Geopolitical risk | GPR composite (VIX/oil proxy + GDELT-ready) | Daily |
| Miner fundamentals | SEC filings (seed data) | Quarterly |

## Model Training

Walk-forward validation with:
- 2-year training window
- 3-month test window
- 1-month step size
- Targets: P(outperform gold), P(beat GDX), expected return

Models tracked in MLflow at `http://localhost:5001`.

## Extending

- **GDELT/ACLED:** Wire into `etl/geopolitical.py` for real NLP-derived GPR
- **WGC API:** Replace seed data in `etl/central_banks.py`
- **SEC EDGAR:** Automate quarterly miner data in `etl/miners.py`
- **LSTM/TFT:** Add to `models/training.py` as ensemble members
- **LLM agents:** Set `OPENAI_API_KEY` for enhanced agent summaries

## License

MIT
