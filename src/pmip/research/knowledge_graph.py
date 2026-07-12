"""Phase 1: Macro knowledge graph with causal hypotheses.

Every edge represents a testable hypothesis about cause and effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import networkx as nx


class Direction(str, Enum):
  POSITIVE = "positive"  # increase in source → increase in target
  NEGATIVE = "negative"  # increase in source → decrease in target
  MIXED = "mixed"


@dataclass
class CausalEdge:
  source: str
  target: str
  direction: Direction
  hypothesis: str
  lag_days: int = 0
  magnitude_hint: str = ""
  evidence_strength: str = "moderate"  # weak, moderate, strong


@dataclass
class MacroNode:
  name: str
  category: str
  description: str
  data_source: str = ""


# Core causal chain from the spec
CORE_EDGES: list[CausalEdge] = [
  CausalEdge(
    source="Fed Policy",
    target="Real Interest Rates",
    direction=Direction.POSITIVE,
    hypothesis="Hawkish Fed guidance raises real yields via higher nominal rates and inflation expectations.",
    lag_days=1,
    magnitude_hint="+25bp Fed hike → +15-30bp real yields",
    evidence_strength="strong",
  ),
  CausalEdge(
    source="Real Interest Rates",
    target="Dollar (DXY)",
    direction=Direction.POSITIVE,
    hypothesis="Higher real yields attract foreign capital, strengthening USD.",
    lag_days=1,
    magnitude_hint="+40bp real yields → DXY +1-2%",
    evidence_strength="strong",
  ),
  CausalEdge(
    source="Dollar (DXY)",
    target="Gold",
    direction=Direction.NEGATIVE,
    hypothesis="Gold is priced in USD; stronger dollar reduces foreign demand and gold's appeal.",
    lag_days=0,
    magnitude_hint="DXY +1% → Gold -0.5 to -1.5%",
    evidence_strength="strong",
  ),
  CausalEdge(
    source="Gold",
    target="Mining Margins",
    direction=Direction.POSITIVE,
    hypothesis="Higher gold prices expand revenue while AISC is relatively fixed short-term.",
    lag_days=0,
    magnitude_hint="Gold +10% → margins expand 15-25% for low-cost producers",
    evidence_strength="strong",
  ),
  CausalEdge(
    source="Mining Margins",
    target="Mining Stocks",
    direction=Direction.POSITIVE,
    hypothesis="Margin expansion drives earnings revisions and equity re-rating.",
    lag_days=5,
    magnitude_hint="Margin +5% → equity +8-15% with operating leverage",
    evidence_strength="moderate",
  ),
]

# Expanded macro relationships
EXPANDED_EDGES: list[CausalEdge] = [
  CausalEdge(
    source="China Demand",
    target="Gold",
    direction=Direction.POSITIVE,
    hypothesis="Chinese retail and institutional demand (jewelry, savings) supports gold prices.",
    lag_days=30,
    magnitude_hint="Strong China PMI → gold +2-4% over 3 months",
    evidence_strength="moderate",
  ),
  CausalEdge(
    source="Central Bank Purchases",
    target="Gold",
    direction=Direction.POSITIVE,
    hypothesis="Structural CB buying removes supply from market, creating persistent bid.",
    lag_days=0,
    magnitude_hint="+100t annual CB buying → ~$8B structural demand",
    evidence_strength="strong",
  ),
  CausalEdge(
    source="Inflation",
    target="Gold",
    direction=Direction.POSITIVE,
    hypothesis="Gold serves as inflation hedge when real yields don't fully compensate.",
    lag_days=5,
    magnitude_hint="CPI surprise +0.3% → gold +1-2% if real yields flat",
    evidence_strength="moderate",
  ),
  CausalEdge(
    source="Oil",
    target="Gold",
    direction=Direction.MIXED,
    hypothesis="Oil spikes signal inflation/stagflation (gold bid) but can tighten financial conditions.",
    lag_days=2,
    magnitude_hint="Oil +10% → gold +1-3% in risk-off; neutral in growth scare",
    evidence_strength="moderate",
  ),
  CausalEdge(
    source="Treasury Yields",
    target="Real Interest Rates",
    direction=Direction.POSITIVE,
    hypothesis="Nominal yield moves drive real yield when breakevens are sticky.",
    lag_days=0,
    magnitude_hint="10Y +50bp with flat breakevens → real yields +50bp",
    evidence_strength="strong",
  ),
  CausalEdge(
    source="VIX",
    target="Gold",
    direction=Direction.POSITIVE,
    hypothesis="Risk-off episodes drive safe-haven gold demand.",
    lag_days=0,
    magnitude_hint="VIX spike +10 → gold +0.5-1.5%",
    evidence_strength="moderate",
  ),
  CausalEdge(
    source="Wars",
    target="Gold",
    direction=Direction.POSITIVE,
    hypothesis="Geopolitical conflict increases safe-haven and de-dollarization demand.",
    lag_days=0,
    magnitude_hint="Major conflict onset → gold +3-8% in first week",
    evidence_strength="strong",
  ),
  CausalEdge(
    source="Sanctions",
    target="Central Bank Purchases",
    direction=Direction.POSITIVE,
    hypothesis="Sanctioned nations accelerate gold reserves to bypass USD system.",
    lag_days=60,
    magnitude_hint="New sanctions regime → CB buying +20-50t annually",
    evidence_strength="moderate",
  ),
  CausalEdge(
    source="ETF Flows",
    target="Gold",
    direction=Direction.POSITIVE,
    hypothesis="GLD/IAU inflows represent marginal price-setting demand.",
    lag_days=1,
    magnitude_hint="+$1B weekly inflows → gold +1-2%",
    evidence_strength="moderate",
  ),
  CausalEdge(
    source="Real Interest Rates",
    target="Mining Stocks",
    direction=Direction.NEGATIVE,
    hypothesis="If real yields rise 40bp, GDX underperforms gold due to discount rate effect.",
    lag_days=5,
    magnitude_hint="+40bp real yields → GDX underperforms gold by 3-8%",
    evidence_strength="strong",
  ),
  CausalEdge(
    source="S&P 500",
    target="Mining Stocks",
    direction=Direction.POSITIVE,
    hypothesis="Risk-on lifts beta-sensitive miners; risk-off hurts despite gold bid.",
    lag_days=0,
    magnitude_hint="SPX +1% → GDX +1.2-2x beta",
    evidence_strength="moderate",
  ),
  CausalEdge(
    source="Copper",
    target="Mining Stocks",
    direction=Direction.POSITIVE,
    hypothesis="Copper reflects global growth; rising copper signals risk-on for miners.",
    lag_days=2,
    magnitude_hint="Copper +5% → miners +2-4% on growth optimism",
    evidence_strength="weak",
  ),
  CausalEdge(
    source="AISC",
    target="Mining Margins",
    direction=Direction.NEGATIVE,
    hypothesis="Rising all-in sustaining costs compress margins even at stable gold prices.",
    lag_days=90,
    magnitude_hint="AISC +$50/oz → margins -3-5%",
    evidence_strength="strong",
  ),
  CausalEdge(
    source="Political Risk",
    target="Mining Stocks",
    direction=Direction.NEGATIVE,
    hypothesis="Jurisdiction risk discounts NAV and increases cost of capital.",
    lag_days=30,
    magnitude_hint="Political risk +1σ → miner discount widens 5-10%",
    evidence_strength="moderate",
  ),
]

NODES: list[MacroNode] = [
  MacroNode("Fed Policy", "monetary", "FOMC decisions, dot plot, Fed speeches", "FRED, Fed"),
  MacroNode("Real Interest Rates", "monetary", "10Y TIPS yield", "FRED"),
  MacroNode("Treasury Yields", "monetary", "2Y and 10Y nominal yields", "FRED"),
  MacroNode("Dollar (DXY)", "fx", "Trade-weighted USD index", "FRED/yfinance"),
  MacroNode("Inflation", "macro", "CPI, PCE, breakevens", "FRED"),
  MacroNode("Gold", "commodity", "COMEX gold futures", "CME/yfinance"),
  MacroNode("Silver", "commodity", "Precious/industrial metal", "yfinance"),
  MacroNode("Copper", "commodity", "Industrial demand proxy", "yfinance"),
  MacroNode("Oil", "commodity", "WTI crude", "yfinance"),
  MacroNode("Natural Gas", "commodity", "Energy input costs", "yfinance"),
  MacroNode("VIX", "volatility", "Equity implied volatility", "FRED/yfinance"),
  MacroNode("S&P 500", "equity", "US equity benchmark", "yfinance"),
  MacroNode("China Demand", "demand", "Chinese gold imports and consumption", "WGC, customs"),
  MacroNode("Central Bank Purchases", "demand", "Official sector gold buying", "WGC"),
  MacroNode("ETF Flows", "demand", "GLD, IAU, SGOL flows", "ETF providers"),
  MacroNode("Wars", "geopolitical", "Active military conflicts", "GDELT, ACLED"),
  MacroNode("Sanctions", "geopolitical", "Trade and financial restrictions", "GDELT, OFAC"),
  MacroNode("Mining Margins", "fundamental", "Revenue - AISC per ounce", "Company filings"),
  MacroNode("AISC", "fundamental", "All-in sustaining cost per oz", "Company filings"),
  MacroNode("Political Risk", "fundamental", "Mine jurisdiction risk score", "Composite"),
  MacroNode("Mining Stocks", "equity", "GDX, individual miners", "yfinance"),
]


def build_knowledge_graph() -> nx.DiGraph:
  """Build the macro causal knowledge graph."""
  g = nx.DiGraph()
  for node in NODES:
    g.add_node(node.name, category=node.category, description=node.description, source=node.data_source)
  for edge in CORE_EDGES + EXPANDED_EDGES:
    g.add_edge(
      edge.source,
      edge.target,
      direction=edge.direction.value,
      hypothesis=edge.hypothesis,
      lag_days=edge.lag_days,
      magnitude_hint=edge.magnitude_hint,
      evidence_strength=edge.evidence_strength,
    )
  return g


def get_hypotheses_for_target(target: str) -> list[CausalEdge]:
  """Return all hypotheses that affect a given variable."""
  all_edges = CORE_EDGES + EXPANDED_EDGES
  return [e for e in all_edges if e.target == target]


def get_transmission_chain(start: str, end: str) -> list[list[str]]:
  """Find all simple paths from start to end in the knowledge graph."""
  g = build_knowledge_graph()
  try:
    return list(nx.all_simple_paths(g, start, end, cutoff=6))
  except (nx.NodeNotFound, nx.NetworkXNoPath):
    return []


@dataclass
class RegimeHypothesis:
  regime_id: int
  name: str
  description: str
  key_drivers: list[str]
  gold_bias: str  # bullish, bearish, neutral
  miner_bias: str
  features: dict[str, str] = field(default_factory=dict)


REGIME_HYPOTHESES: list[RegimeHypothesis] = [
  RegimeHypothesis(
    regime_id=1,
    name="Stagflation / Tightening",
    description="Inflation rising, rates rising, USD rising → gold weak",
    key_drivers=["Inflation", "Real Interest Rates", "Dollar (DXY)"],
    gold_bias="bearish",
    miner_bias="bearish",
    features={"inflation_trend": "rising", "real_yield_trend": "rising", "dxy_trend": "rising"},
  ),
  RegimeHypothesis(
    regime_id=2,
    name="Easing / Dollar Weak",
    description="Inflation falling, Fed easing, dollar falling → gold strong",
    key_drivers=["Fed Policy", "Real Interest Rates", "Dollar (DXY)"],
    gold_bias="bullish",
    miner_bias="bullish",
    features={"inflation_trend": "falling", "real_yield_trend": "falling", "dxy_trend": "falling"},
  ),
  RegimeHypothesis(
    regime_id=3,
    name="Geopolitical Crisis",
    description="War, oil spike, risk-off → gold bid",
    key_drivers=["Wars", "Oil", "VIX"],
    gold_bias="bullish",
    miner_bias="mixed",
    features={"gpr_index": "elevated", "oil_trend": "rising", "vix_level": "high"},
  ),
  RegimeHypothesis(
    regime_id=4,
    name="Recession / Rate Cuts",
    description="Recession, rate cuts, weak dollar → miners outperform",
    key_drivers=["Fed Policy", "S&P 500", "Real Interest Rates"],
    gold_bias="bullish",
    miner_bias="bullish",
    features={"spx_trend": "falling", "real_yield_trend": "falling", "credit_spread": "widening"},
  ),
]
