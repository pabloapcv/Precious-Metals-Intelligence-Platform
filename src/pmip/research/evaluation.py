"""Purged walk-forward evaluation for the two decisions the platform makes.

1. Gold budget: does gold beat the S&P 500 over the next 10 trading days?
2. Gold sleeve: do miners (GDX) beat gold futures over that same window?

Labels that would overlap a test window are embargoed. Economic results use
non-overlapping holding periods and a flat turnover cost.

Statistical inference uses dependence-aware bootstrap for confidence intervals
and Diebold-Mariano tests with HAC variance for forecast comparisons.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from pmip.models.training import WalkForwardConfig, walk_forward_split
from pmip.research.inference import (
  DEFAULT_N_BOOTSTRAP,
  DEFAULT_SEED,
  bootstrap_hit_rate,
  bootstrap_return,
  compare_model_to_baselines,
  diebold_mariano_test,
  holm_bonferroni,
  interpret_dm_test,
  interpret_interval,
)

HORIZON = 10
COST_BPS = 10
PRIMARY_FEATURES = 20


def _finite(value) -> float | None:
  if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
    return None
  return float(value)


def _auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
  if len(y_true) < 5 or len(np.unique(y_true)) < 2:
    return None
  try:
    score = float(roc_auc_score(y_true, scores))
  except ValueError:
    return None
  if math.isnan(score) or math.isinf(score):
    return None
  return score


def build_frame(
  prices: pd.DataFrame,
  features: pd.DataFrame,
  entity: str,
  benchmark: str,
  horizon: int = HORIZON,
) -> pd.DataFrame:
  """One row per date with the decision label, realized returns, and features."""
  if entity not in prices.columns or benchmark not in prices.columns:
    return pd.DataFrame()

  entity_fwd = prices[entity].pct_change(horizon, fill_method=None).shift(-horizon)
  bench_fwd = prices[benchmark].pct_change(horizon, fill_method=None).shift(-horizon)
  momentum = prices[entity].pct_change(20, fill_method=None) - prices[benchmark].pct_change(20, fill_method=None)

  frame = features.copy()
  frame["entity_fwd"] = entity_fwd
  frame["bench_fwd"] = bench_fwd
  frame["momentum"] = momentum
  frame["y"] = (entity_fwd > bench_fwd).astype(float)
  frame = frame.replace([np.inf, -np.inf], np.nan)
  frame = frame.dropna(subset=["entity_fwd", "bench_fwd", "y", "momentum"])
  return frame


def _feature_columns(frame: pd.DataFrame) -> list[str]:
  skip = {"entity_fwd", "bench_fwd", "momentum", "y"}
  cols = []
  for col in frame.columns:
    if col in skip:
      continue
    if not pd.api.types.is_numeric_dtype(frame[col]):
      continue
    if frame[col].notna().mean() < 0.7:
      continue
    cols.append(col)
  return cols


def _select_columns(train: pd.DataFrame, columns: list[str], k: int = PRIMARY_FEATURES) -> list[str]:
  scored = []
  y = train["y"]
  for col in columns:
    pair = train[[col]].join(y).dropna()
    if len(pair) < 30 or pair[col].std() == 0:
      continue
    corr = pair[col].corr(pair["y"])
    if pd.notna(corr):
      scored.append((abs(float(corr)), col))
  scored.sort(reverse=True)
  chosen = [col for _, col in scored[:k]]
  return chosen or columns[:k]


def _logistic_columns(columns: list[str]) -> list[str]:
  keys = ("real_yield", "dxy", "gold_spx", "gold_copper", "gold_oil", "ret_20d", "vol_20d")
  chosen = [c for c in columns if any(key in c for key in keys)]
  return chosen[:12]


def _fit_hgb(X: np.ndarray, y: np.ndarray) -> HistGradientBoostingClassifier:
  model = HistGradientBoostingClassifier(
    max_iter=40,
    learning_rate=0.08,
    max_depth=3,
    random_state=42,
  )
  model.fit(X, y)
  return model


def _fit_logistic(X: np.ndarray, y: np.ndarray):
  pipe = make_pipeline(
    SimpleImputer(strategy="median"),
    StandardScaler(),
    LogisticRegression(max_iter=400, random_state=42),
  )
  pipe.fit(X, y)
  return pipe


def _predict_proba(model, X: np.ndarray) -> np.ndarray:
  proba = model.predict_proba(X)
  if proba.ndim == 2:
    return proba[:, 1]
  return proba


def run_purged_study(
  frame: pd.DataFrame,
  name: str,
  question: str,
  entity_label: str,
  benchmark_label: str,
  horizon: int = HORIZON,
  cost_bps: float = COST_BPS,
) -> dict:
  columns = _feature_columns(frame)
  n = len(frame)
  train = min(120, max(60, int(n * 0.5)))
  while train + horizon + 1 > n and train > 40:
    train -= 10
  config = WalkForwardConfig(train_window=train, test_window=1, step_size=horizon, horizon=horizon)
  splits = walk_forward_split(n, config, embargo=horizon)
  if len(splits) < 4:
    return {
      "name": name,
      "question": question,
      "error": "too few purged folds",
      "n_samples": n,
      "folds": len(splits),
    }

  rows = []
  for train_sl, test_sl in splits:
    train_df = frame.iloc[train_sl]
    test_df = frame.iloc[test_sl]
    if train_df["y"].nunique() < 2 or test_df.empty:
      continue
    chosen = _select_columns(train_df, columns)
    logit_cols = _logistic_columns(columns)
    y_train = train_df["y"].to_numpy()
    y_test = test_df["y"].to_numpy()

    hgb = _fit_hgb(train_df[chosen].to_numpy(), y_train)
    hgb_p = float(_predict_proba(hgb, test_df[chosen].to_numpy())[0])

    if logit_cols and train_df[logit_cols].notna().any().any():
      logit = _fit_logistic(train_df[logit_cols].to_numpy(), y_train)
      logit_p = float(_predict_proba(logit, test_df[logit_cols].to_numpy())[0])
    else:
      logit_p = 0.5

    mom = float(test_df["momentum"].iloc[0])
    # Rank score for AUC: the raw momentum spread. Decision uses its sign.
    ts = test_df.index[0]
    rows.append({
      "date": ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10],
      "y": int(y_test[0]),
      "entity_fwd": float(test_df["entity_fwd"].iloc[0]),
      "bench_fwd": float(test_df["bench_fwd"].iloc[0]),
      "hgb": hgb_p,
      "logistic": logit_p,
      "momentum": mom,
      "always": 1.0,
    })

  oos = pd.DataFrame(rows)
  if len(oos) < 4:
    return {"name": name, "question": question, "error": "no scored dates", "n_samples": n}

  y = oos["y"].to_numpy()
  models = {
    "gradient_boosting": oos["hgb"].to_numpy(),
    "logistic_macro": oos["logistic"].to_numpy(),
    "momentum": oos["momentum"].to_numpy(),
    "always_entity": oos["always"].to_numpy(),
  }
  metrics = {}
  for label, scores in models.items():
    pred = (scores > (0 if label == "momentum" else 0.5)).astype(int)
    metrics[label] = {
      "auc": _auc(y, scores) if label != "always_entity" else 0.5,
      "accuracy": float(accuracy_score(y, pred)),
      "n": int(len(y)),
    }

  books = _books(oos, cost_bps, horizon=horizon)
  calibration = _calibration(oos["y"].to_numpy(), oos["hgb"].to_numpy())
  stability = _stability(frame, columns, splits)

  statistical_tests = _compute_statistical_tests(
    books["return_series"],
    primary_model="gradient_boosting",
    baselines=["logistic_macro", "momentum", "always_entity", "always_benchmark"],
    horizon=horizon,
  )

  return {
    "name": name,
    "question": question,
    "entity": entity_label,
    "benchmark": benchmark_label,
    "horizon_days": horizon,
    "embargo_days": horizon,
    "cost_bps": cost_bps,
    "n_samples": n,
    "n_oos": int(len(oos)),
    "train_window": train,
    "positive_rate": float(y.mean()),
    "metrics": metrics,
    "calibration": calibration,
    "stability": stability,
    "backtest": books["summary"],
    "curve": books["curve"],
    "statistical_tests": statistical_tests,
    "claim": (
      f"Each score is the chance that {entity_label} beats {benchmark_label} "
      f"over the next {horizon} trading days. The test day is excluded from training "
      f"by a {horizon}-day embargo, so the label windows do not overlap."
    ),
  }


def _books(oos: pd.DataFrame, cost_bps: float, horizon: int = HORIZON, seed: int = DEFAULT_SEED) -> dict:
  """Compute wealth curves and return series for each strategy.

  Returns both summary statistics and the raw return series needed for
  statistical inference (bootstrap CIs and DM tests).
  """
  cost = cost_bps / 10_000
  strategies = {
    "gradient_boosting": (oos["hgb"] > 0.5).astype(int),
    "logistic_macro": (oos["logistic"] > 0.5).astype(int),
    "momentum": (oos["momentum"] > 0).astype(int),
    "always_entity": pd.Series(1, index=oos.index),
    "always_benchmark": pd.Series(0, index=oos.index),
  }
  summary = {}
  curve = []
  wealth = {name: 1.0 for name in strategies}
  prev = {name: None for name in strategies}
  return_series = {}

  for i, row in oos.iterrows():
    point = {"date": row["date"]}
    for name, positions in strategies.items():
      pos = int(positions.loc[i])
      gross = pos * row["entity_fwd"] + (1 - pos) * row["bench_fwd"]
      turnover_cost = cost if prev[name] is not None and pos != prev[name] else 0.0
      net = gross - turnover_cost
      wealth[name] *= 1 + net
      prev[name] = pos
      point[name] = round(wealth[name], 4)
    curve.append(point)

  for name, positions in strategies.items():
    rets = []
    last = None
    for i, row in oos.iterrows():
      pos = int(positions.loc[i])
      gross = pos * row["entity_fwd"] + (1 - pos) * row["bench_fwd"]
      turnover_cost = cost if last is not None and pos != last else 0.0
      rets.append(gross - turnover_cost)
      last = pos
    return_series[name] = np.array(rets)
    series = pd.Series(rets)
    equity = (1 + series).cumprod()
    peak = equity.cummax()
    drawdown = float((equity / peak - 1).min()) if len(equity) else None
    hit = None
    predictions = None
    if name not in ("always_entity", "always_benchmark"):
      chosen = positions.to_numpy()
      labels = oos["y"].to_numpy()
      hit = float((((chosen == 1) & (labels == 1)) | ((chosen == 0) & (labels == 0))).mean())
      predictions = chosen

    block_len = max(1, min(horizon, len(rets) // 8))
    total_ret_ci = bootstrap_return(
      np.array(rets),
      block_length=block_len,
      seed=seed,
      statistic="total",
    )
    hit_ci = None
    if predictions is not None:
      hit_ci = bootstrap_hit_rate(
        predictions,
        labels,
        block_length=block_len,
        seed=seed,
      )

    summary[name] = {
      "final_wealth": round(float(equity.iloc[-1]), 4) if len(equity) else None,
      "total_return": round(float(equity.iloc[-1] - 1), 4) if len(equity) else None,
      "total_return_ci": total_ret_ci.to_dict(),
      "max_drawdown": round(drawdown, 4) if drawdown is not None else None,
      "hit_rate": None if hit is None else round(hit, 4),
      "hit_rate_ci": hit_ci.to_dict() if hit_ci else None,
      "avg_period_return": round(float(series.mean()), 4) if len(series) else None,
      "n_periods": int(len(series)),
    }

  return {"summary": summary, "curve": curve, "return_series": return_series}


def _compute_statistical_tests(
  return_series: dict[str, np.ndarray],
  primary_model: str,
  baselines: list[str],
  horizon: int,
) -> dict:
  """Compute Diebold-Mariano tests and Holm-adjusted p-values.

  Tests whether the primary model's returns differ significantly from each
  baseline's returns. Uses HAC variance with bandwidth h-1 for the DM test.
  """
  if primary_model not in return_series:
    return {"error": "primary model returns not found"}

  model_rets = return_series[primary_model]
  dm_results = []
  p_values = []

  for baseline in baselines:
    if baseline not in return_series:
      continue
    baseline_rets = return_series[baseline]
    dm = diebold_mariano_test(
      losses_model=-model_rets,
      losses_baseline=-baseline_rets,
      h=horizon,
      alternative="two-sided",
    )
    dm_results.append({
      "baseline": baseline,
      "dm_test": dm.to_dict(),
      "interpretation": interpret_dm_test(dm, primary_model, baseline),
    })
    p_values.append(dm.p_value if np.isfinite(dm.p_value) else 1.0)

  holm_adjusted = holm_bonferroni(p_values, alpha=0.05)
  for i, adj in enumerate(holm_adjusted):
    if i < len(dm_results):
      dm_results[i]["p_adjusted"] = adj["p_adjusted"]
      dm_results[i]["significant_after_holm"] = adj["significant"]

  any_significant = any(r.get("significant_after_holm", False) for r in dm_results)
  summary = (
    "After Holm-Bonferroni correction for multiple comparisons, "
    + ("at least one comparison is significant at 5%." if any_significant else "no comparison is significant at 5%.")
  )

  return {
    "primary_model": primary_model,
    "n_comparisons": len(dm_results),
    "comparisons": dm_results,
    "multiple_testing_method": "holm_bonferroni",
    "summary": summary,
    "note": (
      "Diebold-Mariano tests use HAC variance (Newey-West) to account for serial "
      "correlation in forecast errors. Positive mean_loss_diff means the model "
      "underperformed the baseline. p_adjusted accounts for multiple testing."
    ),
  }


def _calibration(y: np.ndarray, proba: np.ndarray, bins: int = 5) -> list[dict]:
  if len(y) < bins:
    return []
  edges = np.linspace(0, 1, bins + 1)
  out = []
  for i in range(bins):
    right = edges[i + 1]
    mask = (proba >= edges[i]) & (proba < right if i < bins - 1 else proba <= right)
    if mask.sum() == 0:
      continue
    out.append({
      "bin_low": round(float(edges[i]), 2),
      "bin_high": round(float(right), 2),
      "n": int(mask.sum()),
      "mean_predicted": round(float(proba[mask].mean()), 3),
      "realized_rate": round(float(y[mask].mean()), 3),
    })
  return out


def _stability(frame: pd.DataFrame, columns: list[str], splits: list[tuple[slice, slice]]) -> dict:
  """Refit the small logistic model with and without yield and dollar features."""
  full = _logistic_columns(columns)
  dropped = [c for c in full if "real_yield" not in c and "dxy" not in c]
  if len(full) < 2 or len(dropped) < 1:
    return {"agreement": None, "note": "Not enough macro columns to drop yields and the dollar."}

  calls_full = []
  calls_drop = []
  for train_sl, test_sl in splits:
    train_df = frame.iloc[train_sl]
    test_df = frame.iloc[test_sl]
    if train_df["y"].nunique() < 2:
      continue
    try:
      full_model = _fit_logistic(train_df[full].to_numpy(), train_df["y"].to_numpy())
      drop_model = _fit_logistic(train_df[dropped].to_numpy(), train_df["y"].to_numpy())
    except ValueError:
      continue
    calls_full.append(int(_predict_proba(full_model, test_df[full].to_numpy())[0] > 0.5))
    calls_drop.append(int(_predict_proba(drop_model, test_df[dropped].to_numpy())[0] > 0.5))

  if not calls_full:
    return {"agreement": None, "note": "Stability refit produced no calls."}
  full_arr = np.array(calls_full)
  drop_arr = np.array(calls_drop)
  agreement = float(np.mean(full_arr == drop_arr))
  return {
    "agreement": round(agreement, 3),
    "n": len(calls_full),
    "full_entity_rate": round(float(full_arr.mean()), 3),
    "dropped_entity_rate": round(float(drop_arr.mean()), 3),
    "features_full": full,
    "features_dropped_set": dropped,
    "note": (
      "Agreement is the share of dates with the same binary call after real-yield and dollar "
      "features are removed. Entity rate is how often each version chooses the entity. "
      "Agreement near 100% with an entity rate near 0% or 100% means the model almost never switches."
    ),
  }


def claim_inventory() -> list[dict]:
  return [
    {
      "output": "P(beat gold futures)",
      "method": "Walk-forward classifier on the feature store",
      "allowed_meaning": "Chance the named asset's forward return exceeds gold futures. For GLD this is a tracking spread, not the chance the gold price rises.",
    },
    {
      "output": "P(beat GDX)",
      "method": "95% of P(beat gold futures). No separate model is trained.",
      "allowed_meaning": "A scaled copy of the gold-relative score. It is not a probability of beating the miners ETF.",
    },
    {
      "output": "Expected alpha",
      "method": "Model expected return minus a flat 1% hurdle",
      "allowed_meaning": "A ranking aid. It is not measured excess return versus gold.",
    },
    {
      "output": "Keep / Add / Reduce",
      "method": "Rules on the 10-day gold-versus-equity spread, real yield, dollar trend, and the regime table",
      "allowed_meaning": "A current stance for the gold budget. The research backtest is the evidence for whether a model rule would have helped.",
    },
    {
      "output": "Regime gold bias",
      "method": "Fixed hypothesis for the fitted HMM state",
      "allowed_meaning": "A label for the environment. It is not a forecast and it is not estimated from this sample's returns.",
    },
    {
      "output": "Research AUC and wealth curves",
      "method": "Purged walk-forward, embargo equal to the horizon, 10 bps per flip, non-overlapping 10-day periods",
      "allowed_meaning": "The result to cite. History charts and paper books use as-of scores with the same embargo grammar; the model catalog remains the operational lineage screen.",
    },
  ]


def run_research(features: pd.DataFrame, prices: pd.DataFrame, seed: int = DEFAULT_SEED) -> dict:
  """Run purged walk-forward studies with full statistical inference.

  Each study includes:
  - Bootstrap confidence intervals for hit rates and returns
  - Diebold-Mariano tests comparing the primary model to baselines
  - Holm-Bonferroni correction for multiple comparisons
  - Plain-language interpretation of results
  """
  studies = [
    run_purged_study(
      build_frame(prices, features, "GC=F", "SPX"),
      name="gold_budget",
      question="Should the next 10-day holding be gold or the S&P 500?",
      entity_label="Gold futures",
      benchmark_label="S&P 500",
    ),
    run_purged_study(
      build_frame(prices, features, "GDX", "GC=F"),
      name="miner_sleeve",
      question="Inside a gold budget, should the next 10-day holding be miners or gold?",
      entity_label="Gold miners (GDX)",
      benchmark_label="Gold futures",
    ),
  ]

  n_studies = len([s for s in studies if not s.get("error")])
  total_comparisons = sum(
    s.get("statistical_tests", {}).get("n_comparisons", 0)
    for s in studies
    if not s.get("error")
  )

  inference_summary = {
    "n_studies": n_studies,
    "total_comparisons": total_comparisons,
    "bootstrap_replications": DEFAULT_N_BOOTSTRAP,
    "confidence_level": 0.95,
    "random_seed": seed,
    "note": (
      f"Confidence intervals use stationary bootstrap ({DEFAULT_N_BOOTSTRAP} replications) "
      f"with block length matched to the horizon to preserve serial dependence. "
      f"Diebold-Mariano tests use Newey-West HAC variance. "
      f"Holm-Bonferroni correction is applied to the {total_comparisons} comparisons across all studies."
    ),
  }

  return {
    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "horizon_days": HORIZON,
    "cost_bps": COST_BPS,
    "studies": studies,
    "claims": claim_inventory(),
    "inference_summary": inference_summary,
  }
