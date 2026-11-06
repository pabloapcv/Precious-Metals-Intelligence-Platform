"""Statistical inference for walk-forward evaluation.

Provides dependence-aware bootstrap confidence intervals and forecast comparison
tests (Diebold-Mariano) for the purged research study.

Block length heuristics follow Politis & White (2004) "Automatic Block-Length
Selection" recommendations: for non-overlapping horizon-stepped periods, block
length should roughly equal the horizon to capture intra-period dependence while
allowing enough blocks for stable variance estimation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats


DEFAULT_SEED = 42
DEFAULT_N_BOOTSTRAP = 2000
DEFAULT_CONFIDENCE = 0.95


@dataclass
class ConfidenceInterval:
  """Point estimate with bootstrap confidence interval."""

  estimate: float
  ci_lower: float
  ci_upper: float
  n_bootstrap: int
  confidence: float

  def includes_zero(self) -> bool:
    return self.ci_lower <= 0.0 <= self.ci_upper

  def includes_value(self, value: float) -> bool:
    return self.ci_lower <= value <= self.ci_upper

  def to_dict(self) -> dict:
    return {
      "estimate": round(self.estimate, 4),
      "ci_lower": round(self.ci_lower, 4),
      "ci_upper": round(self.ci_upper, 4),
      "n_bootstrap": self.n_bootstrap,
      "confidence": self.confidence,
    }


@dataclass
class DMTestResult:
  """Result of a Diebold-Mariano test comparing two forecast loss series."""

  statistic: float
  p_value: float
  mean_loss_diff: float
  se: float
  n_obs: int
  hac_lags: int

  def to_dict(self) -> dict:
    return {
      "statistic": round(self.statistic, 4),
      "p_value": round(self.p_value, 4),
      "mean_loss_diff": round(self.mean_loss_diff, 4),
      "se": round(self.se, 4),
      "n_obs": self.n_obs,
      "hac_lags": self.hac_lags,
    }


def _optimal_block_length(n: int, horizon: int) -> int:
  """Choose block length for stationary/circular bootstrap.

  For non-overlapping horizon-stepped returns, the block length should
  roughly equal the horizon since each observation represents a distinct
  economic period. We allow some flexibility but ensure enough blocks
  for stable variance estimation.
  """
  min_blocks = 8
  max_block_size = max(1, n // min_blocks)
  block_length = min(horizon, max_block_size)
  return max(1, block_length)


def _stationary_bootstrap_indices(
  n: int,
  block_length: int,
  rng: np.random.Generator,
) -> np.ndarray:
  """Generate one bootstrap sample using stationary bootstrap.

  The stationary bootstrap (Politis & Romano, 1994) uses geometrically
  distributed block lengths with expected length = block_length.
  This preserves weak dependence structure while avoiding periodic artifacts.
  """
  indices = []
  p = 1.0 / block_length

  while len(indices) < n:
    start = rng.integers(0, n)
    indices.append(start)
    while len(indices) < n and rng.random() > p:
      start = (start + 1) % n
      indices.append(start)

  return np.array(indices[:n])


def _moving_block_indices(
  n: int,
  block_length: int,
  rng: np.random.Generator,
) -> np.ndarray:
  """Generate one bootstrap sample using moving block bootstrap.

  Simpler than stationary bootstrap: sample complete blocks of fixed size.
  """
  n_blocks = (n + block_length - 1) // block_length
  starts = rng.integers(0, n - block_length + 1, size=n_blocks)
  indices = []
  for start in starts:
    indices.extend(range(start, start + block_length))
  return np.array(indices[:n])


def bootstrap_mean(
  data: np.ndarray,
  *,
  block_length: int | None = None,
  n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
  confidence: float = DEFAULT_CONFIDENCE,
  seed: int = DEFAULT_SEED,
  method: str = "stationary",
) -> ConfidenceInterval:
  """Compute bootstrap confidence interval for the mean.

  Args:
    data: 1D array of observations
    block_length: Block size for dependence-aware bootstrap. If None, uses
      a heuristic based on data length.
    n_bootstrap: Number of bootstrap replications
    confidence: Confidence level (e.g. 0.95 for 95% CI)
    seed: Random seed for reproducibility
    method: "stationary" (Politis-Romano) or "block" (moving block)

  Returns:
    ConfidenceInterval with point estimate and percentile CI
  """
  data = np.asarray(data).flatten()
  data = data[np.isfinite(data)]
  n = len(data)

  if n < 3:
    return ConfidenceInterval(
      estimate=float(np.nan),
      ci_lower=float(np.nan),
      ci_upper=float(np.nan),
      n_bootstrap=0,
      confidence=confidence,
    )

  if block_length is None:
    block_length = _optimal_block_length(n, horizon=max(1, n // 10))

  rng = np.random.default_rng(seed)
  estimate = float(np.mean(data))

  means = np.empty(n_bootstrap)
  for i in range(n_bootstrap):
    if method == "stationary":
      idx = _stationary_bootstrap_indices(n, block_length, rng)
    else:
      idx = _moving_block_indices(n, block_length, rng)
    means[i] = np.mean(data[idx])

  alpha = 1 - confidence
  ci_lower = float(np.percentile(means, 100 * alpha / 2))
  ci_upper = float(np.percentile(means, 100 * (1 - alpha / 2)))

  return ConfidenceInterval(
    estimate=estimate,
    ci_lower=ci_lower,
    ci_upper=ci_upper,
    n_bootstrap=n_bootstrap,
    confidence=confidence,
  )


def bootstrap_hit_rate(
  predictions: np.ndarray,
  labels: np.ndarray,
  *,
  block_length: int | None = None,
  n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
  confidence: float = DEFAULT_CONFIDENCE,
  seed: int = DEFAULT_SEED,
) -> ConfidenceInterval:
  """Bootstrap CI for hit rate (accuracy).

  Hit rate is the fraction of correct predictions, treating each observation
  as a 0/1 indicator. Uses stationary bootstrap to handle serial dependence.
  """
  predictions = np.asarray(predictions).flatten()
  labels = np.asarray(labels).flatten()

  hits = (predictions == labels).astype(float)
  return bootstrap_mean(
    hits,
    block_length=block_length,
    n_bootstrap=n_bootstrap,
    confidence=confidence,
    seed=seed,
    method="stationary",
  )


def bootstrap_return(
  returns: np.ndarray,
  *,
  block_length: int | None = None,
  n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
  confidence: float = DEFAULT_CONFIDENCE,
  seed: int = DEFAULT_SEED,
  statistic: str = "total",
) -> ConfidenceInterval:
  """Bootstrap CI for return statistics.

  Args:
    returns: Array of period returns
    statistic: "total" for cumulative return, "mean" for average period return
  """
  returns = np.asarray(returns).flatten()
  returns = returns[np.isfinite(returns)]
  n = len(returns)

  if n < 3:
    return ConfidenceInterval(
      estimate=float(np.nan),
      ci_lower=float(np.nan),
      ci_upper=float(np.nan),
      n_bootstrap=0,
      confidence=confidence,
    )

  if block_length is None:
    block_length = _optimal_block_length(n, horizon=max(1, n // 10))

  rng = np.random.default_rng(seed)

  if statistic == "total":
    estimate = float(np.prod(1 + returns) - 1)
  else:
    estimate = float(np.mean(returns))

  stats_boot = np.empty(n_bootstrap)
  for i in range(n_bootstrap):
    idx = _stationary_bootstrap_indices(n, block_length, rng)
    sample = returns[idx]
    if statistic == "total":
      stats_boot[i] = np.prod(1 + sample) - 1
    else:
      stats_boot[i] = np.mean(sample)

  alpha = 1 - confidence
  ci_lower = float(np.percentile(stats_boot, 100 * alpha / 2))
  ci_upper = float(np.percentile(stats_boot, 100 * (1 - alpha / 2)))

  return ConfidenceInterval(
    estimate=estimate,
    ci_lower=ci_lower,
    ci_upper=ci_upper,
    n_bootstrap=n_bootstrap,
    confidence=confidence,
  )


def _newey_west_var(x: np.ndarray, max_lag: int | None = None) -> float:
  """Newey-West HAC variance estimator for the mean.

  Uses Bartlett kernel weights with automatic lag selection based on
  sample size if max_lag is None.
  """
  x = np.asarray(x).flatten()
  n = len(x)

  if n < 2:
    return float(np.nan)

  if max_lag is None:
    max_lag = int(np.floor(4 * (n / 100) ** (2 / 9)))
  max_lag = max(0, min(max_lag, n - 1))

  x_demean = x - np.mean(x)
  gamma_0 = float(np.dot(x_demean, x_demean) / n)

  var_sum = gamma_0
  for lag in range(1, max_lag + 1):
    weight = 1 - lag / (max_lag + 1)
    gamma_lag = float(np.dot(x_demean[lag:], x_demean[:-lag]) / n)
    var_sum += 2 * weight * gamma_lag

  return var_sum / n


def diebold_mariano_test(
  losses_model: np.ndarray,
  losses_baseline: np.ndarray,
  *,
  h: int = 1,
  alternative: str = "two-sided",
) -> DMTestResult:
  """Diebold-Mariano test for equal predictive accuracy.

  Tests H0: E[d_t] = 0 where d_t = L(model) - L(baseline).
  A negative mean_loss_diff means the model has lower loss than baseline.

  Args:
    losses_model: Loss series for the model being evaluated
    losses_baseline: Loss series for the baseline
    h: Forecast horizon (for HAC bandwidth selection)
    alternative: "two-sided", "less" (model better), or "greater" (baseline better)

  Returns:
    DMTestResult with test statistic, p-value, and diagnostics

  Notes:
    Uses Newey-West HAC variance with bandwidth h-1 following Harvey, Leybourne
    & Newbold (1997) small-sample correction.
  """
  losses_model = np.asarray(losses_model).flatten()
  losses_baseline = np.asarray(losses_baseline).flatten()

  n = len(losses_model)
  if n != len(losses_baseline):
    raise ValueError("Loss series must have equal length")

  if n < 4:
    return DMTestResult(
      statistic=float(np.nan),
      p_value=float(np.nan),
      mean_loss_diff=float(np.nan),
      se=float(np.nan),
      n_obs=n,
      hac_lags=0,
    )

  d = losses_model - losses_baseline
  mean_d = float(np.mean(d))

  hac_lags = max(0, h - 1)
  var_d = _newey_west_var(d, max_lag=hac_lags)

  if var_d <= 0 or not np.isfinite(var_d):
    return DMTestResult(
      statistic=float(np.nan),
      p_value=float(np.nan),
      mean_loss_diff=mean_d,
      se=float(np.nan),
      n_obs=n,
      hac_lags=hac_lags,
    )

  se = float(np.sqrt(var_d))
  dm_stat = mean_d / se

  hln_correction = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
  dm_stat_corrected = dm_stat * hln_correction

  if alternative == "less":
    p_value = float(stats.norm.cdf(dm_stat_corrected))
  elif alternative == "greater":
    p_value = float(1 - stats.norm.cdf(dm_stat_corrected))
  else:
    p_value = float(2 * (1 - stats.norm.cdf(abs(dm_stat_corrected))))

  return DMTestResult(
    statistic=round(dm_stat_corrected, 4),
    p_value=round(p_value, 4),
    mean_loss_diff=mean_d,
    se=se,
    n_obs=n,
    hac_lags=hac_lags,
  )


def holm_bonferroni(p_values: list[float], alpha: float = 0.05) -> list[dict]:
  """Holm-Bonferroni step-down procedure for multiple testing.

  More powerful than Bonferroni while still controlling FWER.

  Args:
    p_values: List of p-values from individual tests
    alpha: Family-wise error rate to control

  Returns:
    List of dicts with original index, p-value, adjusted p-value, and significance
  """
  n = len(p_values)
  if n == 0:
    return []

  indexed = [(i, p) for i, p in enumerate(p_values)]
  sorted_pvals = sorted(indexed, key=lambda x: x[1])

  results = [None] * n
  max_adjusted = 0.0

  for rank, (orig_idx, pval) in enumerate(sorted_pvals):
    k = rank + 1
    adjusted = min(1.0, pval * (n - k + 1))
    adjusted = max(adjusted, max_adjusted)
    max_adjusted = adjusted

    results[orig_idx] = {
      "original_index": orig_idx,
      "p_value": round(pval, 4),
      "p_adjusted": round(adjusted, 4),
      "significant": adjusted < alpha,
      "rank": k,
    }

  return results


def compute_losses_squared_error(
  predictions: np.ndarray,
  actuals: np.ndarray,
) -> np.ndarray:
  """Squared error loss for continuous predictions."""
  return (np.asarray(predictions) - np.asarray(actuals)) ** 2


def compute_losses_economic(
  strategy_returns: np.ndarray,
  baseline_returns: np.ndarray,
) -> np.ndarray:
  """Economic loss: negative excess return (so lower = better).

  When comparing strategy A to baseline B, loss_A = -(return_A - return_B).
  A DM test with mean_loss_diff < 0 means A outperforms B.
  """
  return -(np.asarray(strategy_returns) - np.asarray(baseline_returns))


@dataclass
class ComparisonSummary:
  """Summary of model vs baseline comparisons with uncertainty."""

  model_name: str
  baseline_names: list[str]
  dm_tests: list[DMTestResult]
  adjusted_p_values: list[float]
  significant_at_005: list[bool]

  def to_dict(self) -> dict:
    comparisons = []
    for i, baseline in enumerate(self.baseline_names):
      comparisons.append({
        "baseline": baseline,
        "dm_test": self.dm_tests[i].to_dict(),
        "p_adjusted": round(self.adjusted_p_values[i], 4),
        "significant": self.significant_at_005[i],
      })
    return {
      "model": self.model_name,
      "n_comparisons": len(self.baseline_names),
      "comparisons": comparisons,
    }


def compare_model_to_baselines(
  model_name: str,
  model_returns: np.ndarray,
  baselines: dict[str, np.ndarray],
  *,
  horizon: int = 10,
  alpha: float = 0.05,
) -> ComparisonSummary:
  """Compare a model's economic performance against multiple baselines.

  Runs DM tests for each baseline and applies Holm correction for multiple
  testing.

  Args:
    model_name: Name of the model being evaluated
    model_returns: Period returns of the model
    baselines: Dict mapping baseline names to their return series
    horizon: Forecast horizon (for HAC bandwidth)
    alpha: FWER level for multiple testing

  Returns:
    ComparisonSummary with individual and adjusted test results
  """
  model_returns = np.asarray(model_returns)
  baseline_names = list(baselines.keys())
  dm_tests = []
  p_values = []

  for name in baseline_names:
    baseline_rets = np.asarray(baselines[name])
    losses_model = compute_losses_economic(model_returns, baseline_rets)
    losses_baseline = np.zeros_like(losses_model)

    dm = diebold_mariano_test(
      losses_model,
      losses_baseline,
      h=horizon,
      alternative="two-sided",
    )
    dm_tests.append(dm)
    p_values.append(dm.p_value if np.isfinite(dm.p_value) else 1.0)

  holm_results = holm_bonferroni(p_values, alpha=alpha)
  adjusted = [r["p_adjusted"] for r in holm_results]
  significant = [r["significant"] for r in holm_results]

  return ComparisonSummary(
    model_name=model_name,
    baseline_names=baseline_names,
    dm_tests=dm_tests,
    adjusted_p_values=adjusted,
    significant_at_005=significant,
  )


def interpret_interval(ci: ConfidenceInterval, reference: float = 0.0) -> str:
  """Generate plain-language interpretation of a confidence interval."""
  if not np.isfinite(ci.estimate):
    return "insufficient data for inference"

  pct = int(ci.confidence * 100)
  width = ci.ci_upper - ci.ci_lower

  if ci.includes_value(reference):
    return f"{pct}% CI [{ci.ci_lower:.3f}, {ci.ci_upper:.3f}] includes {reference}, so no significant difference at this level"

  direction = "above" if ci.ci_lower > reference else "below"
  return f"{pct}% CI [{ci.ci_lower:.3f}, {ci.ci_upper:.3f}] is entirely {direction} {reference}"


def interpret_dm_test(dm: DMTestResult, model_name: str, baseline_name: str) -> str:
  """Generate plain-language interpretation of a DM test result."""
  if not np.isfinite(dm.p_value):
    return f"insufficient data to compare {model_name} vs {baseline_name}"

  if dm.p_value < 0.01:
    sig = "highly significant (p<0.01)"
  elif dm.p_value < 0.05:
    sig = "significant at 5%"
  elif dm.p_value < 0.10:
    sig = "marginally significant (p<0.10)"
  else:
    sig = "not significant"

  direction = "outperforms" if dm.mean_loss_diff < 0 else "underperforms"
  return f"{model_name} {direction} {baseline_name} by {abs(dm.mean_loss_diff):.4f} per period ({sig}, p={dm.p_value:.3f})"
