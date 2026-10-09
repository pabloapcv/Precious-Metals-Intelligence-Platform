"""Phase 9: FastAPI backend serving predictions and dashboard data."""

from __future__ import annotations

import logging
import math
from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pmip.api.explain_service import get_explainability
from pmip.api.history_service import get_history
from pmip.api.macro_service import build_macro_snapshot
from pmip.api.research_service import (
  get_macro_series,
  get_model_catalog,
  get_portfolio_analytics,
  get_regime_history,
  get_research_desk,
  get_signal_book,
)
from pmip import __version__
from pmip.agents.research import run_all_agents
from pmip.config import get_settings
from pmip.constants import ALL_MINERS, PREDICTION_TARGETS
from pmip.db.models import (
  CentralBankPurchase,
  ETFFlow,
  GeopoliticalRisk,
  MacroDaily,
  MarketRegime,
  MinerQuarterly,
  ModelPrediction,
  PortfolioRecommendation,
)
from pmip.db.session import get_db, get_db_session
from pmip.models.regime import get_current_regime
from pmip.pipeline.runner import run_full_pipeline
from pmip.research.knowledge_graph import (
  REGIME_HYPOTHESES,
  build_knowledge_graph,
  get_hypotheses_for_target,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


def _safe_float(value, default: float | None = 0.0) -> float | None:
  """Coerce DB/agent values; None/NaN/inf fall back to default."""
  if value is None:
    return default
  try:
    num = float(value)
  except (TypeError, ValueError):
    return default
  if math.isnan(num) or math.isinf(num):
    return default
  return num

app = FastAPI(
  title="Precious Metals Macro Intelligence Platform",
  description="Institutional-grade gold & mining analytics with regime detection and ML predictions",
  version=__version__,
)

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


# ── Response schemas ─────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
  status: str
  version: str
  timestamp: str


class MacroSnapshot(BaseModel):
  date: str
  gold_price: float | None
  dxy: float | None
  real_yield: float | None
  vix: float | None
  spx: float | None


class PredictionItem(BaseModel):
  rank: int
  entity: str
  label: str
  tier: str
  prob_outperform_gold: float
  expected_alpha: float
  horizon_days: int


class DashboardResponse(BaseModel):
  as_of: str
  macro: dict
  commodities: dict
  gold: dict
  regime: dict | None
  mining_companies: list[PredictionItem]
  risk: dict
  portfolio: list[dict]
  agent_scores: dict
  etf_flows: dict
  central_banks: dict
  insights: list[str]
  data_status: dict


@app.on_event("startup")
def on_startup():
  settings = get_settings()
  logger.info("PMIP API starting — database: %s", settings.database_url)
  with get_db_session() as session:
    macro_count = session.query(MacroDaily).count()
    pred_count = session.query(ModelPrediction).count()
    logger.info("Database rows — macro: %d, predictions: %d", macro_count, pred_count)
    if macro_count == 0:
      logger.warning("Database empty — click 'Run Pipeline' or run: make pipeline")


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
def root():
  """Serve the React dashboard at the API root (avoids 404 on localhost:8000)."""
  index = FRONTEND_DIST / "index.html"
  if index.exists():
    return FileResponse(index)
  return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse)
def health():
  return HealthResponse(status="ok", version=__version__, timestamp=datetime.utcnow().isoformat())


@app.get("/api/v1/macro/snapshot", response_model=MacroSnapshot)
def macro_snapshot(db: Session = Depends(get_db)):
  snap = build_macro_snapshot(db)
  return MacroSnapshot(
    date=snap["as_of"],
    gold_price=snap.get("gold_price"),
    dxy=snap.get("dxy"),
    real_yield=snap.get("real_yields"),
    vix=snap.get("vix"),
    spx=snap.get("spx"),
  )


@app.get("/api/v1/knowledge-graph")
def knowledge_graph():
  g = build_knowledge_graph()
  nodes = [{"id": n, **g.nodes[n]} for n in g.nodes]
  edges = [{"source": u, "target": v, **g.edges[u, v]} for u, v in g.edges]
  return {"nodes": nodes, "edges": edges}


@app.get("/api/v1/hypotheses/{target}")
def hypotheses(target: str):
  edges = get_hypotheses_for_target(target)
  return {
    "target": target,
    "hypotheses": [
      {
        "source": e.source,
        "direction": e.direction.value,
        "hypothesis": e.hypothesis,
        "lag_days": e.lag_days,
        "magnitude_hint": e.magnitude_hint,
        "evidence_strength": e.evidence_strength,
      }
      for e in edges
    ],
  }


@app.get("/api/v1/regimes")
def regimes():
  return {
    "regimes": [
      {
        "id": r.regime_id,
        "name": r.name,
        "description": r.description,
        "gold_bias": r.gold_bias,
        "miner_bias": r.miner_bias,
        "key_drivers": r.key_drivers,
      }
      for r in REGIME_HYPOTHESES
    ],
  }


@app.get("/api/v1/regime/current")
def current_regime(db: Session = Depends(get_db)):
  regime = get_current_regime(db)
  if not regime:
    raise HTTPException(404, "No regime detected yet. Run pipeline first.")
  return regime


@app.get("/api/v1/predictions")
def predictions(horizon: int = 10, db: Session = Depends(get_db)):
  rows = (
    db.query(ModelPrediction)
    .filter(ModelPrediction.horizon_days == horizon)
    .order_by(ModelPrediction.prob_outperform_gold.desc())
    .all()
  )
  label_map = {t["entity"]: t for t in PREDICTION_TARGETS}
  return [
    {
      "entity": r.entity,
      "label": label_map.get(r.entity, {}).get("label", r.entity),
      "tier": label_map.get(r.entity, {}).get("tier", "unknown"),
      "prob_outperform_gold": r.prob_outperform_gold,
      "prob_beat_gdx": r.prob_beat_gdx,
      "expected_return": r.expected_return,
      "expected_alpha": r.expected_alpha,
      "horizon_days": r.horizon_days,
      "date": r.date.isoformat(),
    }
    for r in rows
  ]


@app.get("/api/v1/dashboard", response_model=DashboardResponse)
def dashboard(db: Session = Depends(get_db)):
  """Morning dashboard — the core institutional output."""
  try:
    return _build_dashboard(db)
  except Exception as exc:
    logger.exception("Dashboard endpoint failed")
    raise HTTPException(status_code=500, detail=str(exc)) from exc


def _model_walk_forward_summary(db: Session) -> dict:
  catalog = get_model_catalog(db)
  aucs = [
    m["walk_forward"]["mean_auc"]
    for m in catalog
    if m["walk_forward"]["mean_auc"] is not None
  ]
  if aucs:
    return {"mean_auc": round(sum(aucs) / len(aucs), 3), "n_models": len(catalog)}
  return {"mean_auc": None, "n_models": len(catalog)}


def _build_dashboard(db: Session) -> DashboardResponse:
  macro = build_macro_snapshot(db)
  regime = get_current_regime(db)

  gold_pred = (
    db.query(ModelPrediction)
    .filter(ModelPrediction.entity == "GLD", ModelPrediction.horizon_days == 10)
    .order_by(ModelPrediction.date.desc())
    .first()
  )
  gold_bullish = _safe_float(gold_pred.prob_outperform_gold if gold_pred else None, 0.55)
  gold_expected_alpha = _safe_float(gold_pred.expected_alpha if gold_pred else None, 0.0)

  miner_entities = [m["ticker"] for m in ALL_MINERS] + ["GDX", "GDXJ", "RING"]
  miner_preds = (
    db.query(ModelPrediction)
    .filter(ModelPrediction.entity.in_(miner_entities), ModelPrediction.horizon_days == 10)
    .order_by(ModelPrediction.expected_alpha.desc())
    .all()
  )
  label_map = {t["entity"]: t for t in PREDICTION_TARGETS}
  mining_companies = [
    PredictionItem(
      rank=i + 1,
      entity=p.entity,
      label=label_map.get(p.entity, {}).get("label", p.entity),
      tier=label_map.get(p.entity, {}).get("tier", "senior"),
      prob_outperform_gold=_safe_float(p.prob_outperform_gold, 0.5),
      expected_alpha=_safe_float(p.expected_alpha, 0.0),
      horizon_days=p.horizon_days,
    )
    for i, p in enumerate(miner_preds[:10])
  ]

  gpr = db.query(GeopoliticalRisk).order_by(GeopoliticalRisk.date.desc()).first()
  etf_gld = db.query(ETFFlow).filter(ETFFlow.ticker == "GLD").order_by(ETFFlow.date.desc()).first()
  etf_iau = db.query(ETFFlow).filter(ETFFlow.ticker == "IAU").order_by(ETFFlow.date.desc()).first()
  cb = db.query(CentralBankPurchase).order_by(CentralBankPurchase.month.desc()).limit(12).all()
  cb_total = sum(float(c.purchase_tonnes or 0) for c in cb)

  risk = {
    "war_probability": "rising" if gpr and _safe_float(gpr.gpr_index, 0) > 0.5 else "stable",
    "oil_disruption": "rising" if gpr and _safe_float(gpr.oil_disruption, 0) > 0.4 else "stable",
    "central_bank_buying": "rising" if cb_total > 30 else "stable",
    "etf_flows": "declining" if etf_gld and _safe_float(etf_gld.daily_flow, 0) < 0 else "stable",
    "gpr_index": _safe_float(gpr.gpr_index, None) if gpr else None,
    "conflict_intensity": _safe_float(gpr.conflict_intensity, None) if gpr else None,
  }

  portfolio_rows = (
    db.query(PortfolioRecommendation)
    .order_by(PortfolioRecommendation.date.desc(), PortfolioRecommendation.rank)
    .limit(10)
    .all()
  )
  portfolio = [
    {
      "rank": p.rank,
      "ticker": p.ticker,
      "weight": _safe_float(p.weight, 0.0),
      "expected_alpha": _safe_float(p.expected_alpha, 0.0),
    }
    for p in portfolio_rows
  ]

  miner_fundamentals = {}
  for m in ALL_MINERS:
    q = (
      db.query(MinerQuarterly)
      .filter(MinerQuarterly.ticker == m["ticker"])
      .order_by(MinerQuarterly.quarter_end.desc())
      .first()
    )
    if q:
      miner_fundamentals[m["ticker"]] = {
        "analyst_eps_revision": float(q.analyst_eps_revision or 0),
        "aisc_per_oz": float(q.aisc_per_oz or 0),
        "production_oz": float(q.production_oz or 0),
        "management_confidence": 0.6,
      }

  agent_context = {
    "real_yield": _safe_float(macro.get("real_yields"), 2.0),
    "dxy_trend": _safe_float(macro.get("dxy_trend_20d_pct"), 0.0) / 100,
    "inflation_trend": 0.05,
    "vix": _safe_float(macro.get("vix"), 15.0),
    "gpr_index": _safe_float(gpr.gpr_index if gpr else None, 0.3),
    "oil_disruption": _safe_float(gpr.oil_disruption if gpr else None, 0.2),
    "conflict_intensity": _safe_float(gpr.conflict_intensity if gpr else None, 0.2),
    "miners": miner_fundamentals,
    "regime": regime or {},
    "walk_forward": _model_walk_forward_summary(db),
    "feature_importance": {"real_yield_trend_20d": 0.18, "dxy_zscore": 0.15, "gpr_index": 0.12},
  }
  agent_outputs = run_all_agents(agent_context)
  agent_scores = {name: out.scores for name, out in agent_outputs.items()}

  # Actionable insights from live data
  insights: list[str] = []
  if macro.get("real_yields") is not None:
    if macro["real_yields"] > 2.0:
      insights.append(f"Real yields at {macro['real_yields']:.2f}% are a headwind for gold — watch Fed guidance.")
    else:
      insights.append(f"Real yields at {macro['real_yields']:.2f}% support gold relative to cash.")
  if macro.get("dxy_trend_20d_pct") is not None:
    if macro["dxy_trend_20d_pct"] < -1:
      insights.append(f"Dollar weakening ({macro['dxy_trend_20d_pct']:+.1f}% over 20d) — historically gold-positive.")
    elif macro["dxy_trend_20d_pct"] > 1:
      insights.append(f"Dollar strengthening ({macro['dxy_trend_20d_pct']:+.1f}% over 20d) — pressure on gold.")
  if regime:
    insights.append(f"Current regime: {regime['regime_name']} — miners may have asymmetric leverage here.")
  if cb_total > 30:
    insights.append(f"Central banks bought ~{cb_total:.0f}t in recent months — structural demand support.")
  if mining_companies:
    top = mining_companies[0]
    insights.append(
      f"Top miner pick: {top.label} with {top.expected_alpha * 100:.1f}% expected alpha vs gold (10d)."
    )
  if not insights:
    insights.append("Run the pipeline to populate live macro, regime, and miner signals.")

  regime_detail = None
  if regime:
    match = next((r for r in REGIME_HYPOTHESES if r.regime_id == regime.get("regime_id")), None)
    regime_detail = {
      **regime,
      "description": match.description if match else "",
      "gold_bias": match.gold_bias if match else "neutral",
      "miner_bias": match.miner_bias if match else "neutral",
      "key_drivers": match.key_drivers if match else [],
    }

  macro_count = db.query(MacroDaily).count()
  pred_count = db.query(ModelPrediction).count()

  return DashboardResponse(
    as_of=macro["as_of"],
    macro={
      "fed_probability": macro["fed_probability"],
      "dollar_strength": macro["dollar_strength"],
      "real_yields": macro.get("real_yields"),
      "real_yield_source": macro.get("real_yield_source"),
      "nominal_10y": macro.get("nominal_10y"),
      "breakeven_10y": macro.get("breakeven_10y"),
      "inflation": macro["inflation"],
      "vix": macro.get("vix"),
      "dxy": macro.get("dxy"),
      "dxy_trend_20d_pct": macro.get("dxy_trend_20d_pct"),
      "gold_trend_20d_pct": macro.get("gold_trend_20d_pct"),
    },
    commodities={
      "gold": macro.get("gold_price"),
      "silver": macro.get("silver_price"),
      "oil": macro.get("oil_price"),
      "copper": macro.get("copper_price"),
      "spx": macro.get("spx"),
      "gdx": macro.get("gdx_price"),
    },
    gold={
      "bullish_pct": round(gold_bullish * 100),
      "target_horizon_days": 10,
      "signal": "bullish" if gold_bullish > 0.55 else ("bearish" if gold_bullish < 0.45 else "neutral"),
      "expected_alpha_pct": round(gold_expected_alpha * 100, 2),
      "price": macro.get("gold_price"),
    },
    regime=regime_detail,
    mining_companies=mining_companies,
    risk=risk,
    portfolio=portfolio,
    agent_scores=agent_scores,
    etf_flows={
      "gld_daily_m": float(etf_gld.daily_flow) if etf_gld and etf_gld.daily_flow else None,
      "gld_30d_avg_m": float(etf_gld.flow_30d_avg) if etf_gld and etf_gld.flow_30d_avg else None,
      "iau_daily_m": float(etf_iau.daily_flow) if etf_iau and etf_iau.daily_flow else None,
      "signal": risk["etf_flows"],
    },
    central_banks={
      "recent_purchases_tonnes": cb_total,
      "top_buyers": [
        {"country": c.country, "tonnes": float(c.purchase_tonnes or 0)}
        for c in cb[:5]
      ],
      "signal": risk["central_bank_buying"],
    },
    insights=insights,
    data_status={
      "macro_rows": macro_count,
      "predictions": pred_count,
      "has_regime": regime is not None,
      "has_portfolio": len(portfolio) > 0,
      "pipeline_needed": macro_count == 0 or pred_count == 0,
    },
  )


@app.post("/api/v1/pipeline/run")
def run_pipeline():
  """Trigger full ETL → features → regime → training → predictions pipeline."""
  try:
    return run_full_pipeline()
  except Exception as e:
    logger.exception("Pipeline failed")
    raise HTTPException(500, f"Pipeline failed: {e}") from e


@app.get("/api/v1/etf-flows")
def etf_flows(db: Session = Depends(get_db), ticker: str = "GLD"):
  rows = db.query(ETFFlow).filter(ETFFlow.ticker == ticker).order_by(ETFFlow.date.desc()).limit(60).all()
  return [
    {
      "date": r.date.isoformat(),
      "daily_flow": float(r.daily_flow) if r.daily_flow else None,
      "weekly_flow": float(r.weekly_flow) if r.weekly_flow else None,
      "flow_30d_avg": float(r.flow_30d_avg) if r.flow_30d_avg else None,
      "flow_60d_avg": float(r.flow_60d_avg) if r.flow_60d_avg else None,
    }
    for r in rows
  ]


@app.get("/api/v1/central-banks")
def central_banks(db: Session = Depends(get_db)):
  rows = db.query(CentralBankPurchase).order_by(CentralBankPurchase.month.desc()).limit(100).all()
  return [
    {
      "month": r.month.isoformat(),
      "country": r.country,
      "purchase_tonnes": float(r.purchase_tonnes) if r.purchase_tonnes else None,
      "rolling_12m_tonnes": float(r.rolling_12m_tonnes) if r.rolling_12m_tonnes else None,
      "yoy_growth_pct": float(r.yoy_growth_pct) if r.yoy_growth_pct else None,
    }
    for r in rows
  ]


@app.get("/api/v1/research")
def research_desk(db: Session = Depends(get_db)):
  """Institutional research desk — signals, models, regime history, portfolio analytics."""
  try:
    return get_research_desk(db)
  except Exception as exc:
    logger.exception("Research desk endpoint failed")
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/regime/history")
def regime_history(db: Session = Depends(get_db), days: int = 120):
  return {"history": get_regime_history(db, days=days)}


@app.get("/api/v1/macro/series")
def macro_series(
  db: Session = Depends(get_db),
  symbols: str = "GC=F,DX-Y.NYB,GDX,US10Y_REAL,VIX",
  days: int = 252,
):
  sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
  return {"series": get_macro_series(db, sym_list, days=days)}


@app.get("/api/v1/models/catalog")
def models_catalog(db: Session = Depends(get_db)):
  catalog = get_model_catalog(db)
  aucs = [
    m["walk_forward"]["mean_auc"]
    for m in catalog
    if m["walk_forward"]["mean_auc"] is not None and not (
      isinstance(m["walk_forward"]["mean_auc"], float) and math.isnan(m["walk_forward"]["mean_auc"])
    )
  ]
  return {
    "models": catalog,
    "summary": {
      "n_models": len(catalog),
      "mean_auc": round(sum(aucs) / len(aucs), 3) if aucs else None,
    },
  }


@app.get("/api/v1/signals")
def signals(horizon: int = 10, db: Session = Depends(get_db)):
  return {"horizon_days": horizon, "signals": get_signal_book(db, horizon=horizon)}


@app.get("/api/v1/explain")
def explain(db: Session = Depends(get_db)):
  """Full process transparency — pipeline, agents, signal rules, walkthroughs."""
  try:
    return get_explainability(db)
  except Exception as exc:
    logger.exception("Explain endpoint failed")
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/history")
def history(
  db: Session = Depends(get_db),
  days: int = 180,
  horizon: int = 10,
  backfill: bool = True,
):
  """Historical outlook, regime, and macro series for charts."""
  try:
    return get_history(db, days=days, horizon=horizon, ensure_backfill=backfill)
  except Exception as exc:
    logger.exception("History endpoint failed")
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/portfolio/analytics")
def portfolio_analytics(db: Session = Depends(get_db)):
  return get_portfolio_analytics(db)


if (FRONTEND_DIST / "assets").is_dir():
  app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")
