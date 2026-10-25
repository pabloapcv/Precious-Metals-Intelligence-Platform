#!/usr/bin/env python3
"""Reproduce the purged walk-forward study and write the research artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pmip.db.session import get_db_session
from pmip.features.engineering import load_feature_matrix
from pmip.models.training import _build_price_panel
from pmip.research.evaluation import run_research


def _pct(value, digits=1) -> str:
  if value is None:
    return "—"
  return f"{value * 100:.{digits}f}%"


def _num(value, digits=3) -> str:
  if value is None:
    return "—"
  return f"{value:.{digits}f}"


def _results_markdown(payload: dict) -> str:
  lines = [
    "# Latest research results",
    "",
    f"Generated {payload['generated_at']}. Horizon {payload['horizon_days']} trading days. "
    f"Turnover cost {payload['cost_bps']} bps when a book flips. "
    "Each test date is embargoed by one full horizon, and wealth compounds only on those non-overlapping dates.",
    "",
  ]
  for study in payload["studies"]:
    lines.append(f"## {study.get('question', study.get('name'))}")
    lines.append("")
    if study.get("error"):
      lines.append(f"Study did not complete: {study['error']} (samples {study.get('n_samples')}, folds {study.get('folds')}).")
      lines.append("")
      continue
    lines.append(
      f"Sample {study['n_samples']} labeled days, {study['n_oos']} out-of-sample dates, "
      f"train window {study['train_window']}, positive rate {_pct(study['positive_rate'])}."
    )
    lines.append("")
    lines.append("| Model | AUC | Accuracy | Final wealth | Total return | Max drawdown | Hit rate |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    order = ["gradient_boosting", "logistic_macro", "momentum", "always_entity", "always_benchmark"]
    labels = {
      "gradient_boosting": "Gradient boosting",
      "logistic_macro": "Logistic, macro features",
      "momentum": "20-day relative momentum",
      "always_entity": f"Always {study['entity']}",
      "always_benchmark": f"Always {study['benchmark']}",
    }
    for key in order:
      metric = study["metrics"].get(key, {})
      book = study["backtest"].get(key, {})
      lines.append(
        "| {name} | {auc} | {acc} | {wealth} | {ret} | {dd} | {hit} |".format(
          name=labels[key],
          auc=_num(metric.get("auc")) if metric else "—",
          acc=_pct(metric.get("accuracy"), 1) if metric else "—",
          wealth=_num(book.get("final_wealth"), 3),
          ret=_pct(book.get("total_return"), 1),
          dd=_pct(book.get("max_drawdown"), 1),
          hit=_pct(book.get("hit_rate"), 1) if book.get("hit_rate") is not None else "—",
        )
      )
    lines.append("")
    lines.append("Calibration of the gradient-boosted probabilities:")
    lines.append("")
    lines.append("| Predicted bin | Count | Mean predicted | Realized rate |")
    lines.append("| --- | ---: | ---: | ---: |")
    for row in study["calibration"]:
      lines.append(
        f"| {row['bin_low']:.2f}–{row['bin_high']:.2f} | {row['n']} | {row['mean_predicted']:.3f} | {row['realized_rate']:.3f} |"
      )
    if not study["calibration"]:
      lines.append("| — | — | — | — |")
    stab = study["stability"]
    lines.append("")
    lines.append(
      f"Stability: agreement after dropping real yield and the dollar is {_pct(stab.get('agreement'), 1)} "
      f"across {stab.get('n', 0)} dates. "
      f"The full logistic chooses the entity on {_pct(stab.get('full_entity_rate'), 1)} of dates; "
      f"without yields and the dollar, on {_pct(stab.get('dropped_entity_rate'), 1)}. "
      f"{stab.get('note', '')}"
    )
    lines.append("")
  lines.append("## What each on-screen number is allowed to mean")
  lines.append("")
  lines.append("| Output | Method | Allowed meaning |")
  lines.append("| --- | --- | --- |")
  for claim in payload["claims"]:
    lines.append(f"| {claim['output']} | {claim['method']} | {claim['allowed_meaning']} |")
  lines.append("")
  return "\n".join(lines)


def main() -> None:
  out_dir = ROOT / "docs" / "research"
  out_dir.mkdir(parents=True, exist_ok=True)
  with get_db_session() as session:
    features = load_feature_matrix(session)
    prices = _build_price_panel(session)
  if features.empty or prices.empty:
    raise SystemExit("Feature store or prices are empty. Run make pipeline first.")

  payload = run_research(features, prices)
  (out_dir / "results.json").write_text(json.dumps(payload, indent=2))
  (out_dir / "latest-results.md").write_text(_results_markdown(payload))

  note = ROOT / "docs" / "research-note.md"
  if note.exists():
    text = note.read_text()
    start = "<!-- RESULTS:START -->"
    end = "<!-- RESULTS:END -->"
    block = start + "\n\n" + _results_markdown(payload) + "\n" + end
    if start in text and end in text:
      text = text[: text.index(start)] + block + text[text.index(end) + len(end) :]
      note.write_text(text)

  for study in payload["studies"]:
    if study.get("error"):
      print(study["name"], study["error"])
      continue
    hgb = study["metrics"]["gradient_boosting"]
    base = study["backtest"]["always_benchmark"]
    model = study["backtest"]["gradient_boosting"]
    print(
      f"{study['name']}: n={study['n_oos']} auc={hgb['auc']} "
      f"model_wealth={model['final_wealth']} benchmark_wealth={base['final_wealth']}"
    )


if __name__ == "__main__":
  main()
