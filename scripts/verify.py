#!/usr/bin/env python3
"""Verify the platform works end-to-end."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main() -> int:
  from pmip.config import get_settings
  from pmip.db.models import MacroDaily, ModelPrediction
  from pmip.db.session import get_db_session
  from pmip.pipeline.runner import run_full_pipeline

  settings = get_settings()
  print(f"Database: {settings.database_url}")

  # Ensure schema exists
  from pmip.db.models import Base
  from pmip.db.session import get_engine

  if settings.database_url.startswith("sqlite"):
    db_path = Path(settings.database_url.replace("sqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
      db_path.unlink()
  Base.metadata.create_all(bind=get_engine())
  print("✓ Database schema OK")

  # Run pipeline
  print("Running full pipeline (this may take a few minutes)...")
  result = run_full_pipeline(
    lookback_days=365,
    train_entities=["GLD", "GDX"],
  )
  print(f"✓ Pipeline: {json.dumps({k: v for k, v in result.items() if k != 'train_results'}, indent=2)}")

  with get_db_session() as session:
    macro_count = session.query(MacroDaily).count()
    pred_count = session.query(ModelPrediction).count()
    print(f"✓ Macro rows: {macro_count}")
    print(f"✓ Predictions: {pred_count}")

    if macro_count == 0:
      print("✗ FAIL: No macro data ingested")
      return 1
    if pred_count == 0:
      print("✗ FAIL: No predictions generated")
      return 1

  # API smoke test
  from pmip.api.main import app
  from fastapi.testclient import TestClient

  client = TestClient(app)
  health = client.get("/health")
  assert health.status_code == 200, health.text
  print("✓ API /health OK")

  dashboard = client.get("/api/v1/dashboard")
  assert dashboard.status_code == 200, dashboard.text
  data = dashboard.json()
  print(f"✓ Dashboard: gold bullish {data['gold']['bullish_pct']}%, miners ranked {len(data['mining_companies'])}")

  print("\nAll checks passed.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
