"""Pipeline run presets and option resolution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from pmip.constants import HORIZONS, PREDICTION_TARGETS, horizon_label
from pmip.models.asof import ASOF_ENTITIES
from pmip.pipeline.progress import STAGES

ALL_STAGE_IDS = [stage_id for stage_id, _label, _weight in STAGES]


@dataclass
class PipelineRunConfig:
  stages: list[str] = field(default_factory=lambda: list(ALL_STAGE_IDS))
  horizons: list[int] = field(default_factory=lambda: list(HORIZONS))
  train_scope: str = "all"  # all | liquid
  walk_forward: bool = True
  lookback_days: int = 365 * 2
  preset: str | None = None

  def resolved_entities(self) -> list[str]:
    if self.train_scope == "liquid":
      scored = {t["entity"] for t in PREDICTION_TARGETS}
      return [e for e in ASOF_ENTITIES if e in scored]
    return [t["entity"] for t in PREDICTION_TARGETS]

  def to_dict(self) -> dict:
    return {
      **asdict(self),
      "entities": self.resolved_entities(),
      "horizon_labels": {str(h): horizon_label(h) for h in self.horizons},
      "n_models": len(self.resolved_entities()) * len(self.horizons),
    }


PRESETS: dict[str, dict] = {
  "quick_prices": {
    "id": "quick_prices",
    "label": "Refresh prices",
    "blurb": "Pull market data, rebuild features, refresh the regime. No training.",
    "eta": "2–5 min",
    "stages": ["etl", "features", "regime"],
    "horizons": list(HORIZONS),
    "train_scope": "liquid",
    "walk_forward": False,
    "lookback_days": 365 * 2,
  },
  "signals": {
    "id": "signals",
    "label": "Rescore signals",
    "blurb": "Score the latest day with existing models and rebuild the portfolio.",
    "eta": "1–3 min",
    "stages": ["predict", "portfolio"],
    "horizons": list(HORIZONS),
    "train_scope": "all",
    "walk_forward": False,
    "lookback_days": 365 * 2,
  },
  "short_train": {
    "id": "short_train",
    "label": "Train short horizons",
    "blurb": "Liquid sleeve · 5d / 10d / 1m only · skip walk-forward for speed.",
    "eta": "10–25 min",
    "stages": ["train", "predict", "portfolio"],
    "horizons": [5, 10, 20],
    "train_scope": "liquid",
    "walk_forward": False,
    "lookback_days": 365 * 2,
  },
  "paper": {
    "id": "paper",
    "label": "Rebuild paper books",
    "blurb": "Purged as-of history + paper books. Defaults to short horizons; add 3m/6m if you need them.",
    "eta": "15–40 min",
    "stages": ["history", "paper"],
    "horizons": [5, 10, 20],
    "train_scope": "liquid",
    "walk_forward": False,
    "lookback_days": 365 * 2,
  },
  "full": {
    "id": "full",
    "label": "Full pipeline",
    "blurb": "Everything: prices through models, as-of history, and all paper books.",
    "eta": "1–3+ hrs",
    "stages": list(ALL_STAGE_IDS),
    "horizons": list(HORIZONS),
    "train_scope": "all",
    "walk_forward": True,
    "lookback_days": 365 * 2,
  },
}


def describe_options() -> dict:
  return {
    "stages": [
      {"id": stage_id, "label": label, "weight": weight}
      for stage_id, label, weight in STAGES
    ],
    "horizons": [
      {"days": h, "label": horizon_label(h)}
      for h in HORIZONS
    ],
    "train_scopes": [
      {"id": "liquid", "label": "Liquid sleeve", "blurb": f"{len(ASOF_ENTITIES)} liquid names used for as-of / paper"},
      {"id": "all", "label": "Full scored universe", "blurb": f"{len(PREDICTION_TARGETS)} modeled entities"},
    ],
    "presets": list(PRESETS.values()),
    "defaults": PipelineRunConfig().to_dict(),
  }


def resolve_config(payload: dict | None) -> PipelineRunConfig:
  raw = dict(payload or {})
  preset_id = raw.pop("preset", None)
  base: dict = {}
  if preset_id and preset_id in PRESETS:
    preset = PRESETS[preset_id]
    base = {
      "stages": list(preset["stages"]),
      "horizons": list(preset["horizons"]),
      "train_scope": preset["train_scope"],
      "walk_forward": preset["walk_forward"],
      "lookback_days": preset["lookback_days"],
      "preset": preset_id,
    }
  # Explicit fields override the preset.
  for key in ("stages", "horizons", "train_scope", "walk_forward", "lookback_days"):
    if key in raw and raw[key] is not None:
      base[key] = raw[key]
  if preset_id and "preset" not in base:
    base["preset"] = preset_id

  stages = [s for s in (base.get("stages") or ALL_STAGE_IDS) if s in ALL_STAGE_IDS]
  if not stages:
    stages = list(ALL_STAGE_IDS)
  horizons = [int(h) for h in (base.get("horizons") or HORIZONS) if int(h) in HORIZONS]
  if not horizons:
    horizons = list(HORIZONS)
  scope = base.get("train_scope") or "all"
  if scope not in ("all", "liquid"):
    scope = "all"

  return PipelineRunConfig(
    stages=stages,
    horizons=horizons,
    train_scope=scope,
    walk_forward=bool(base.get("walk_forward", True)),
    lookback_days=int(base.get("lookback_days") or 365 * 2),
    preset=base.get("preset"),
  )
