"""Tests for PMIP."""

import pytest


def test_knowledge_graph_builds():
  from pmip.research.knowledge_graph import build_knowledge_graph

  g = build_knowledge_graph()
  assert g.number_of_nodes() > 10
  assert g.number_of_edges() > 10


def test_regime_hypotheses_defined():
  from pmip.research.knowledge_graph import REGIME_HYPOTHESES

  assert len(REGIME_HYPOTHESES) == 4


def test_macro_symbols_defined():
  from pmip.constants import MACRO_SYMBOLS, PREDICTION_TARGETS

  assert len(MACRO_SYMBOLS) >= 10
  assert any(t["entity"] == "GLD" for t in PREDICTION_TARGETS)


def test_hypotheses_for_gold():
  from pmip.research.knowledge_graph import get_hypotheses_for_target

  hypotheses = get_hypotheses_for_target("Gold")
  assert len(hypotheses) >= 3
  sources = {h.source for h in hypotheses}
  assert "Dollar (DXY)" in sources or "Real Interest Rates" in sources
