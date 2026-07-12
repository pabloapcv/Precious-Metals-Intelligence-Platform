"""Phase 8: AI research agents."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from pmip.config import get_settings

logger = logging.getLogger(__name__)


def _safe_float(value, default: float = 0.0) -> float:
  if value is None:
    return default
  try:
    return float(value)
  except (TypeError, ValueError):
    return default


@dataclass
class AgentOutput:
  agent_name: str
  timestamp: str
  scores: dict[str, float] = field(default_factory=dict)
  summary: str = ""
  signals: list[str] = field(default_factory=list)
  confidence: float = 0.5


class BaseAgent(ABC):
  def __init__(self, name: str):
    self.name = name
    self.settings = get_settings()

  @abstractmethod
  def analyze(self, context: dict) -> AgentOutput:
    pass

  def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
    """Call LLM for analysis. Falls back to rule-based if no API key."""
    if self.settings.openai_api_key:
      try:
        from openai import OpenAI
        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.chat.completions.create(
          model="gpt-4o-mini",
          messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
          ],
          temperature=0.3,
          max_tokens=1000,
        )
        return response.choices[0].message.content or ""
      except Exception as e:
        logger.warning("OpenAI call failed: %s", e)
    return ""


class MacroAgent(BaseAgent):
  """Reads Fed policy, yields, inflation, dollar. Outputs Macro Score."""

  def __init__(self):
    super().__init__("MacroAgent")

  def analyze(self, context: dict) -> AgentOutput:
    real_yield = context.get("real_yield", 2.0)
    dxy_trend = context.get("dxy_trend", 0)
    inflation_trend = context.get("inflation_trend", 0)
    vix = context.get("vix", 15)

    # Rule-based scoring (LLM enhances in production)
    macro_score = 0.5
    signals = []

    if real_yield < 1.5:
      macro_score += 0.15
      signals.append("Low real yields support gold")
    elif real_yield > 2.5:
      macro_score -= 0.15
      signals.append("Elevated real yields headwind for gold")

    if dxy_trend < -0.02:
      macro_score += 0.1
      signals.append("Weakening dollar supports gold")
    elif dxy_trend > 0.02:
      macro_score -= 0.1
      signals.append("Strong dollar pressures gold")

    if inflation_trend > 0.1:
      macro_score += 0.05
      signals.append("Rising inflation expectations gold-positive")

    macro_score = max(0, min(1, macro_score))

    llm_context = json.dumps(context, default=str)
    llm_summary = self._call_llm(
      "You are a macro strategist specializing in gold and precious metals. "
      "Provide a 2-3 sentence macro assessment.",
      f"Analyze this macro context for gold: {llm_context}",
    )

    return AgentOutput(
      agent_name=self.name,
      timestamp=datetime.utcnow().isoformat(),
      scores={"macro_score": macro_score, "gold_bullishness": macro_score},
      summary=llm_summary or f"Macro score {macro_score:.0%}: real yields {real_yield:.2f}%, DXY trend {dxy_trend:+.1%}",
      signals=signals,
      confidence=0.7,
    )


class GeopoliticalAgent(BaseAgent):
  """Reads news, OSINT, conflict data. Outputs Conflict Score and Energy Risk."""

  def __init__(self):
    super().__init__("GeopoliticalAgent")

  def analyze(self, context: dict) -> AgentOutput:
    gpr = _safe_float(context.get("gpr_index"), 0.3)
    oil_disruption = _safe_float(context.get("oil_disruption"), 0.2)
    conflict = _safe_float(context.get("conflict_intensity"), 0.2)

    conflict_score = min(1, conflict * 1.2)
    energy_risk = min(1, oil_disruption * 1.5)
    gold_bullishness = min(1, 0.3 + gpr * 0.5 + conflict * 0.2)

    signals = []
    if gpr > 0.5:
      signals.append("Elevated geopolitical risk supports safe-haven demand")
    if oil_disruption > 0.4:
      signals.append("Oil disruption risk elevated — stagflation tailwind for gold")
    if conflict > 0.5:
      signals.append("Active conflict intensity increasing")

    return AgentOutput(
      agent_name=self.name,
      timestamp=datetime.utcnow().isoformat(),
      scores={
        "conflict_score": conflict_score,
        "energy_risk": energy_risk,
        "gold_bullishness": gold_bullishness,
      },
      summary=f"GPR index {gpr:.2f}: conflict {conflict:.2f}, oil disruption {oil_disruption:.2f}",
      signals=signals,
      confidence=0.65,
    )


class MiningAgent(BaseAgent):
  """Reads filings, earnings, production reports. Outputs fundamental scores."""

  def __init__(self):
    super().__init__("MiningAgent")

  def analyze(self, context: dict) -> AgentOutput:
    miners = context.get("miners", {})
    signals = []
    scores = {}

    for ticker, data in miners.items():
      aisc_trend = data.get("aisc_trend", 0)
      prod_surprise = data.get("prod_surprise", 0)
      revision = data.get("analyst_eps_revision", 0)
      confidence = data.get("management_confidence", 0.5)

      fundamental_score = 0.5 + prod_surprise * 0.2 - aisc_trend * 0.15 + revision * 0.3
      fundamental_score = max(0, min(1, fundamental_score))
      scores[f"{ticker}_fundamental"] = fundamental_score

      if prod_surprise > 0.03:
        signals.append(f"{ticker}: positive production surprise")
      if revision > 0.02:
        signals.append(f"{ticker}: upward EPS revisions")

    avg_score = np_mean(list(scores.values())) if scores else 0.5

    return AgentOutput(
      agent_name=self.name,
      timestamp=datetime.utcnow().isoformat(),
      scores=scores | {"avg_fundamental": avg_score},
      summary=f"Analyzed {len(miners)} miners, avg fundamental score {avg_score:.0%}",
      signals=signals,
      confidence=0.75,
    )


class QuantAgent(BaseAgent):
  """Runs factor models, backtests, SHAP analysis. Outputs signal stability."""

  def __init__(self):
    super().__init__("QuantAgent")

  def analyze(self, context: dict) -> AgentOutput:
    wf_results = context.get("walk_forward", {})
    feature_importance = context.get("feature_importance", {})
    regime = context.get("regime", {})

    mean_auc = wf_results.get("mean_auc", 0.5)
    signal_stability = min(1, mean_auc)

    top_features = sorted(feature_importance.items(), key=lambda x: -x[1])[:5]
    signals = [f"Top driver: {f[0]} ({f[1]:.2f})" for f in top_features]
    if regime:
      signals.append(f"Current regime: {regime.get('regime_name', 'unknown')}")

    return AgentOutput(
      agent_name=self.name,
      timestamp=datetime.utcnow().isoformat(),
      scores={
        "signal_stability": signal_stability,
        "mean_auc": mean_auc,
        "model_confidence": signal_stability * 0.9,
      },
      summary=f"Walk-forward AUC {mean_auc:.3f}, signal stability {signal_stability:.0%}",
      signals=signals,
      confidence=signal_stability,
    )


def np_mean(vals: list[float]) -> float:
  return sum(vals) / len(vals) if vals else 0.0


def run_all_agents(context: dict) -> dict[str, AgentOutput]:
  agents = [MacroAgent(), GeopoliticalAgent(), MiningAgent(), QuantAgent()]
  return {a.name: a.analyze(context) for a in agents}
