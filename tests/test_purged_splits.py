"""Embargo keeps training labels out of the test window."""

from pmip.models.training import WalkForwardConfig, walk_forward_split


def test_embargo_gap_is_at_least_the_horizon():
  horizon = 10
  config = WalkForwardConfig(train_window=40, test_window=1, step_size=horizon, horizon=horizon)
  splits = walk_forward_split(120, config, embargo=horizon)
  assert len(splits) >= 3
  for train_sl, test_sl in splits:
    assert train_sl.stop <= test_sl.start - horizon
    assert train_sl.stop - train_sl.start == 40
