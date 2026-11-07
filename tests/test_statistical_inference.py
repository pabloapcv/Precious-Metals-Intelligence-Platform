"""Unit tests for statistical inference (bootstrap and Diebold-Mariano tests).

Tests include known-answer cases and property-based checks to ensure the
bootstrap and DM test implementations are correct.
"""

from __future__ import annotations

import numpy as np
import pytest

from pmip.research.inference import (
  ConfidenceInterval,
  DMTestResult,
  bootstrap_mean,
  bootstrap_hit_rate,
  bootstrap_return,
  diebold_mariano_test,
  holm_bonferroni,
  compare_model_to_baselines,
  interpret_interval,
  interpret_dm_test,
  _newey_west_var,
  _stationary_bootstrap_indices,
)


class TestBootstrapMean:
  """Tests for bootstrap_mean function."""

  def test_known_iid_mean(self):
    """For IID data, bootstrap CI should contain true mean with high probability."""
    rng = np.random.default_rng(42)
    data = rng.normal(5.0, 1.0, 100)

    ci = bootstrap_mean(data, seed=42, n_bootstrap=1000)

    assert isinstance(ci, ConfidenceInterval)
    assert 4.5 <= ci.estimate <= 5.5
    assert ci.ci_lower < ci.estimate < ci.ci_upper
    assert ci.confidence == 0.95

  def test_deterministic_with_seed(self):
    """Same seed should produce identical results."""
    data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])

    ci1 = bootstrap_mean(data, seed=123, n_bootstrap=500)
    ci2 = bootstrap_mean(data, seed=123, n_bootstrap=500)

    assert ci1.estimate == ci2.estimate
    assert ci1.ci_lower == ci2.ci_lower
    assert ci1.ci_upper == ci2.ci_upper

  def test_different_seeds_different_results(self):
    """Different seeds should produce different CIs."""
    data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])

    ci1 = bootstrap_mean(data, seed=100, n_bootstrap=500)
    ci2 = bootstrap_mean(data, seed=200, n_bootstrap=500)

    assert ci1.ci_lower != ci2.ci_lower or ci1.ci_upper != ci2.ci_upper

  def test_small_sample_returns_nan(self):
    """Samples with fewer than 3 observations should return NaN."""
    data = np.array([1.0, 2.0])
    ci = bootstrap_mean(data)
    assert np.isnan(ci.estimate)
    assert ci.n_bootstrap == 0

  def test_constant_data_narrow_ci(self):
    """Constant data should yield a very narrow or zero-width CI."""
    data = np.array([5.0] * 20)
    ci = bootstrap_mean(data, seed=42)
    assert ci.estimate == 5.0
    assert ci.ci_lower == 5.0
    assert ci.ci_upper == 5.0


class TestBootstrapHitRate:
  """Tests for bootstrap_hit_rate function."""

  def test_perfect_predictions(self):
    """Perfect predictions should have hit rate near 1.0."""
    predictions = np.array([1, 0, 1, 1, 0, 0, 1, 1, 0, 1])
    labels = np.array([1, 0, 1, 1, 0, 0, 1, 1, 0, 1])

    ci = bootstrap_hit_rate(predictions, labels, seed=42)

    assert ci.estimate == 1.0
    assert ci.ci_lower == 1.0
    assert ci.ci_upper == 1.0

  def test_random_predictions_around_half(self):
    """Random predictions should have hit rate CI around 0.5."""
    rng = np.random.default_rng(42)
    labels = rng.integers(0, 2, 100)
    predictions = rng.integers(0, 2, 100)

    ci = bootstrap_hit_rate(predictions, labels, seed=42)

    assert 0.3 <= ci.ci_lower <= 0.5
    assert 0.5 <= ci.ci_upper <= 0.7

  def test_known_hit_rate(self):
    """Test with known 80% hit rate. Block bootstrap produces wider CIs."""
    predictions = np.array([1] * 80 + [0] * 20)
    labels = np.array([1] * 80 + [1] * 20)

    ci = bootstrap_hit_rate(predictions, labels, seed=42)

    assert ci.estimate == 0.8
    assert ci.ci_lower < ci.estimate
    assert ci.ci_upper > ci.estimate
    assert 0.0 <= ci.ci_lower <= 1.0
    assert 0.0 <= ci.ci_upper <= 1.0


class TestBootstrapReturn:
  """Tests for bootstrap_return function."""

  def test_positive_returns(self):
    """All positive returns should have positive total return CI."""
    returns = np.array([0.01, 0.02, 0.01, 0.03, 0.01, 0.02, 0.01, 0.02, 0.01, 0.02])

    ci = bootstrap_return(returns, seed=42, statistic="total")

    assert ci.estimate > 0
    assert ci.ci_lower > 0
    assert ci.ci_upper > ci.ci_lower

  def test_known_total_return(self):
    """Test calculation of total return."""
    returns = np.array([0.10, 0.10, 0.10])
    expected = (1.1 * 1.1 * 1.1) - 1

    ci = bootstrap_return(returns, seed=42, statistic="total")

    assert abs(ci.estimate - expected) < 0.001

  def test_mean_vs_total(self):
    """Mean statistic should differ from total statistic."""
    returns = np.array([0.05, 0.05, 0.05, 0.05, 0.05])

    ci_total = bootstrap_return(returns, seed=42, statistic="total")
    ci_mean = bootstrap_return(returns, seed=42, statistic="mean")

    assert ci_total.estimate != ci_mean.estimate
    assert ci_mean.estimate == pytest.approx(0.05, rel=0.01)


class TestDieboldMarianoTest:
  """Tests for diebold_mariano_test function."""

  def test_identical_losses_no_difference(self):
    """Identical loss series should give mean diff of 0 (NaN p-value is acceptable for zero variance)."""
    losses = np.random.default_rng(42).normal(0, 1, 50)

    dm = diebold_mariano_test(losses, losses, h=1)

    assert dm.mean_loss_diff == 0.0
    assert np.isnan(dm.p_value) or dm.p_value >= 0.5

  def test_clearly_different_losses(self):
    """Very different losses should give low p-value."""
    rng = np.random.default_rng(42)
    losses_model = rng.normal(0, 0.1, 50)
    losses_baseline = rng.normal(1, 0.1, 50)

    dm = diebold_mariano_test(losses_model, losses_baseline, h=1)

    assert dm.mean_loss_diff < -0.5
    assert dm.p_value < 0.05

  def test_one_sided_less(self):
    """One-sided test (model better) should have p-value <= two-sided."""
    rng = np.random.default_rng(42)
    losses_model = rng.normal(0, 0.5, 40)
    losses_baseline = rng.normal(0.5, 0.5, 40)

    dm_two = diebold_mariano_test(losses_model, losses_baseline, h=1, alternative="two-sided")
    dm_less = diebold_mariano_test(losses_model, losses_baseline, h=1, alternative="less")

    assert dm_less.p_value <= dm_two.p_value
    assert dm_less.p_value < 0.05  # model clearly better

  def test_small_sample_returns_nan(self):
    """Very small samples should return NaN."""
    losses = np.array([1.0, 2.0, 3.0])
    dm = diebold_mariano_test(losses, losses, h=1)
    assert np.isnan(dm.p_value)

  def test_hac_lags_scale_with_horizon(self):
    """HAC lags should be h-1."""
    losses = np.random.default_rng(42).normal(0, 1, 50)

    dm_h1 = diebold_mariano_test(losses, losses + 0.1, h=1)
    dm_h5 = diebold_mariano_test(losses, losses + 0.1, h=5)
    dm_h10 = diebold_mariano_test(losses, losses + 0.1, h=10)

    assert dm_h1.hac_lags == 0
    assert dm_h5.hac_lags == 4
    assert dm_h10.hac_lags == 9


class TestNeweyWestVariance:
  """Tests for Newey-West HAC variance estimator."""

  def test_iid_same_as_simple(self):
    """For IID data, HAC should be close to simple variance."""
    rng = np.random.default_rng(42)
    x = rng.normal(0, 1, 200)

    nw_var = _newey_west_var(x, max_lag=0)
    simple_var = np.var(x, ddof=0) / len(x)

    assert abs(nw_var - simple_var) < 0.01

  def test_autocorrelated_larger_variance(self):
    """Autocorrelated data should have larger HAC variance than simple variance."""
    rng = np.random.default_rng(42)
    n = 200
    x = np.zeros(n)
    x[0] = rng.normal()
    for i in range(1, n):
      x[i] = 0.7 * x[i-1] + rng.normal()

    nw_var = _newey_west_var(x, max_lag=10)
    simple_var = np.var(x, ddof=0) / n

    assert nw_var > simple_var


class TestHolmBonferroni:
  """Tests for Holm-Bonferroni multiple testing correction."""

  def test_single_p_value(self):
    """Single p-value should be unchanged."""
    results = holm_bonferroni([0.03], alpha=0.05)

    assert len(results) == 1
    assert results[0]["p_value"] == 0.03
    assert results[0]["p_adjusted"] == 0.03
    assert results[0]["significant"] is True

  def test_bonferroni_bound(self):
    """Holm should be at least as powerful as Bonferroni."""
    p_values = [0.01, 0.02, 0.03, 0.04]
    n = len(p_values)

    results = holm_bonferroni(p_values, alpha=0.05)

    for r in results:
      bonferroni_adj = min(1.0, r["p_value"] * n)
      assert r["p_adjusted"] <= bonferroni_adj + 0.0001

  def test_known_example(self):
    """Test with a known worked example."""
    p_values = [0.01, 0.04, 0.03, 0.005]

    results = holm_bonferroni(p_values, alpha=0.05)
    by_rank = {r["rank"]: r for r in results}

    assert by_rank[1]["p_value"] == 0.005
    assert by_rank[1]["p_adjusted"] == 0.02
    assert by_rank[1]["significant"] is True

    assert by_rank[2]["p_value"] == 0.01
    assert by_rank[2]["p_adjusted"] == 0.03
    assert by_rank[2]["significant"] is True

  def test_preserves_order(self):
    """Results should preserve original index."""
    p_values = [0.5, 0.01, 0.1]
    results = holm_bonferroni(p_values)

    assert results[0]["original_index"] == 0
    assert results[1]["original_index"] == 1
    assert results[2]["original_index"] == 2

  def test_monotonicity(self):
    """Adjusted p-values should be monotone non-decreasing in rank order."""
    p_values = [0.01, 0.03, 0.02, 0.05, 0.04]
    results = holm_bonferroni(p_values)
    sorted_by_rank = sorted(results, key=lambda r: r["rank"])
    adj = [r["p_adjusted"] for r in sorted_by_rank]

    for i in range(len(adj) - 1):
      assert adj[i] <= adj[i + 1]


class TestCompareModelToBaselines:
  """Tests for compare_model_to_baselines function."""

  def test_model_outperforms_all(self):
    """Model clearly outperforming all baselines should show in comparisons."""
    rng = np.random.default_rng(42)
    model_returns = rng.normal(0.02, 0.01, 50)
    baselines = {
      "baseline_a": rng.normal(0.005, 0.01, 50),
      "baseline_b": rng.normal(0.003, 0.01, 50),
    }

    result = compare_model_to_baselines("model", model_returns, baselines, horizon=10)

    assert result.model_name == "model"
    assert len(result.baseline_names) == 2
    assert len(result.dm_tests) == 2

  def test_holm_correction_applied(self):
    """Multiple baselines should have Holm-corrected p-values."""
    rng = np.random.default_rng(42)
    model_returns = rng.normal(0.01, 0.01, 50)
    baselines = {f"baseline_{i}": rng.normal(0.01, 0.01, 50) for i in range(5)}

    result = compare_model_to_baselines("model", model_returns, baselines)

    assert len(result.adjusted_p_values) == 5
    for p_raw, p_adj in zip([dm.p_value for dm in result.dm_tests], result.adjusted_p_values):
      if np.isfinite(p_raw):
        assert p_adj >= p_raw


class TestInterpretFunctions:
  """Tests for plain-language interpretation functions."""

  def test_interpret_interval_includes_zero(self):
    """CI including zero should say 'no significant difference'."""
    ci = ConfidenceInterval(
      estimate=0.1,
      ci_lower=-0.05,
      ci_upper=0.25,
      n_bootstrap=1000,
      confidence=0.95,
    )

    text = interpret_interval(ci, reference=0.0)

    assert "includes 0" in text
    assert "no significant" in text

  def test_interpret_interval_above_reference(self):
    """CI entirely above reference should say so."""
    ci = ConfidenceInterval(
      estimate=0.15,
      ci_lower=0.05,
      ci_upper=0.25,
      n_bootstrap=1000,
      confidence=0.95,
    )

    text = interpret_interval(ci, reference=0.0)

    assert "above 0" in text

  def test_interpret_dm_test_significant(self):
    """Significant DM test should mention significance level."""
    dm = DMTestResult(
      statistic=-2.5,
      p_value=0.01,
      mean_loss_diff=-0.02,
      se=0.008,
      n_obs=50,
      hac_lags=9,
    )

    text = interpret_dm_test(dm, "model", "baseline")

    assert "model" in text
    assert "baseline" in text
    assert "significant" in text.lower()


class TestStationaryBootstrapIndices:
  """Tests for the stationary bootstrap index generator."""

  def test_correct_length(self):
    """Generated indices should have correct length."""
    rng = np.random.default_rng(42)
    indices = _stationary_bootstrap_indices(100, 10, rng)
    assert len(indices) == 100

  def test_valid_range(self):
    """All indices should be in valid range."""
    rng = np.random.default_rng(42)
    for _ in range(10):
      indices = _stationary_bootstrap_indices(50, 5, rng)
      assert all(0 <= i < 50 for i in indices)

  def test_reproducible_with_seed(self):
    """Same RNG state should produce same indices."""
    indices1 = _stationary_bootstrap_indices(100, 10, np.random.default_rng(42))
    indices2 = _stationary_bootstrap_indices(100, 10, np.random.default_rng(42))
    np.testing.assert_array_equal(indices1, indices2)


class TestConfidenceIntervalMethods:
  """Tests for ConfidenceInterval dataclass methods."""

  def test_includes_zero_true(self):
    ci = ConfidenceInterval(-0.1, -0.2, 0.1, 1000, 0.95)
    assert ci.includes_zero() is True

  def test_includes_zero_false(self):
    ci = ConfidenceInterval(0.3, 0.1, 0.5, 1000, 0.95)
    assert ci.includes_zero() is False

  def test_includes_value(self):
    ci = ConfidenceInterval(0.5, 0.3, 0.7, 1000, 0.95)
    assert ci.includes_value(0.5) is True
    assert ci.includes_value(0.35) is True
    assert ci.includes_value(0.1) is False

  def test_to_dict(self):
    ci = ConfidenceInterval(0.1234, 0.0567, 0.1901, 1000, 0.95)
    d = ci.to_dict()
    assert d["estimate"] == 0.1234
    assert d["ci_lower"] == 0.0567
    assert d["ci_upper"] == 0.1901
    assert d["n_bootstrap"] == 1000
    assert d["confidence"] == 0.95
