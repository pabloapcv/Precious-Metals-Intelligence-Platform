"""In-memory progress for the long pipeline run."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

STAGES: list[tuple[str, str, int]] = [
  ("etl", "Market data", 10),
  ("features", "Features", 12),
  ("regime", "Regime", 4),
  ("train", "Models", 58),
  ("predict", "Predictions", 6),
  ("history", "History", 6),
  ("portfolio", "Portfolio", 2),
  ("paper", "Paper", 2),
]

LOG_LIMIT = 80


def _now() -> str:
  return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PipelineTracker:
  def __init__(self) -> None:
    self._lock = threading.Lock()
    self._state = self._idle()

  def _idle(self, stage_ids: list[str] | None = None) -> dict:
    selected = stage_ids or [stage_id for stage_id, _label, _weight in STAGES]
    selected_set = set(selected)
    return {
      "status": "idle",
      "started_at": None,
      "finished_at": None,
      "message": "Ready",
      "error": None,
      "config": None,
      "stages": [
        {"id": stage_id, "label": label, "status": "pending", "detail": "", "done": 0, "total": 0}
        for stage_id, label, _weight in STAGES
        if stage_id in selected_set
      ],
      "current": {
        "stage": None,
        "action": None,
        "item": None,
        "done": 0,
        "total": 0,
        "unit": None,
      },
      "train": {"done": 0, "total": 0, "entity": None, "horizon": None},
      "log": [],
    }

  def begin(self, stages: list[str] | None = None, config: dict | None = None) -> bool:
    with self._lock:
      if self._state["status"] == "running":
        return False
      state = self._idle(stages)
      state["status"] = "running"
      state["started_at"] = _now()
      state["message"] = "Starting"
      state["config"] = config
      self._state = state
      label = (config or {}).get("preset") or "custom"
      self._append_log("pipeline", f"Pipeline started ({label})")
      return True

  def report(
    self,
    stage: str,
    *,
    status: str = "running",
    detail: str = "",
    done: int | None = None,
    total: int | None = None,
    entity: str | None = None,
    horizon: int | None = None,
    action: str | None = None,
    item: str | None = None,
    unit: str | None = None,
    log: bool = True,
  ) -> None:
    with self._lock:
      if self._state["status"] != "running":
        return

      for entry in self._state["stages"]:
        if entry["id"] == stage:
          entry["status"] = status
          if detail:
            entry["detail"] = detail
          if done is not None:
            entry["done"] = done
          if total is not None:
            entry["total"] = total
        elif status == "running" and entry["status"] == "running" and entry["id"] != stage:
          entry["status"] = "done"

      current = self._state["current"]
      current["stage"] = stage
      if action is not None:
        current["action"] = action
      if item is not None:
        current["item"] = item
      if done is not None:
        current["done"] = done
      if total is not None:
        current["total"] = total
      if unit is not None:
        current["unit"] = unit

      # Keep the older train block populated so existing UI still works.
      if stage == "train":
        if done is not None:
          self._state["train"]["done"] = done
        if total is not None:
          self._state["train"]["total"] = total
        if entity is not None:
          self._state["train"]["entity"] = entity
        if horizon is not None:
          self._state["train"]["horizon"] = horizon

      message = detail
      if not message and action and item:
        message = f"{action}: {item}"
      elif not message and action:
        message = action
      self._state["message"] = message or next(
        (entry["label"] for entry in self._state["stages"] if entry["id"] == stage),
        stage,
      )

      if log and (detail or item or action):
        line = detail or (f"{action}: {item}" if action and item else action or item or stage)
        if done is not None and total is not None and total > 0:
          line = f"{line} ({done}/{total})"
        self._append_log(stage, line)

  def finish(self, message: str = "Pipeline complete") -> None:
    with self._lock:
      for entry in self._state["stages"]:
        if entry["status"] in ("pending", "running"):
          entry["status"] = "done"
      self._state["status"] = "complete"
      self._state["finished_at"] = _now()
      self._state["message"] = message
      self._state["error"] = None
      self._state["current"] = {
        "stage": None,
        "action": None,
        "item": None,
        "done": self._state["current"].get("done", 0),
        "total": self._state["current"].get("total", 0),
        "unit": None,
      }
      self._append_log("pipeline", message)

  def fail(self, error: str) -> None:
    with self._lock:
      for entry in self._state["stages"]:
        if entry["status"] == "running":
          entry["status"] = "error"
      self._state["status"] = "failed"
      self._state["finished_at"] = _now()
      self._state["error"] = error
      self._state["message"] = error
      self._append_log("pipeline", f"Failed: {error}")

  def snapshot(self) -> dict:
    with self._lock:
      return {
        "status": self._state["status"],
        "started_at": self._state["started_at"],
        "finished_at": self._state["finished_at"],
        "message": self._state["message"],
        "error": self._state["error"],
        "stages": [dict(entry) for entry in self._state["stages"]],
        "current": dict(self._state["current"]),
        "train": dict(self._state["train"]),
        "log": list(self._state["log"]),
        "config": dict(self._state["config"]) if self._state.get("config") else None,
        "percent": self._percent(),
        "elapsed_seconds": self._elapsed(),
      }

  def _append_log(self, stage: str, text: str) -> None:
    self._state["log"].append({"at": _now(), "stage": stage, "text": text})
    if len(self._state["log"]) > LOG_LIMIT:
      self._state["log"] = self._state["log"][-LOG_LIMIT:]

  def _elapsed(self) -> float | None:
    started = self._state.get("started_at")
    if not started:
      return None
    start = datetime.fromisoformat(started)
    end_raw = self._state.get("finished_at")
    end = datetime.fromisoformat(end_raw) if end_raw else datetime.now(timezone.utc)
    if start.tzinfo is None:
      start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
      end = end.replace(tzinfo=timezone.utc)
    return round((end - start).total_seconds(), 1)

  def _percent(self) -> float:
    by_id = {entry["id"]: entry for entry in self._state["stages"]}
    if not by_id:
      return 0.0
    # Renormalize weights over the stages selected for this run.
    weight_map = {stage_id: weight for stage_id, _label, weight in STAGES if stage_id in by_id}
    total_weight = sum(weight_map.values()) or 1.0
    percent = 0.0
    for stage_id, weight in weight_map.items():
      share = 100.0 * weight / total_weight
      entry = by_id.get(stage_id, {})
      status = entry.get("status", "pending")
      if status == "done":
        percent += share
      elif status == "running":
        done = entry.get("done") or 0
        total = entry.get("total") or 0
        if total > 0:
          percent += share * min(done / total, 1)
        else:
          percent += share * 0.15
    return round(min(percent, 100), 1)


TRACKER = PipelineTracker()
