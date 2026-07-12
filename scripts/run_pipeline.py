#!/usr/bin/env python3
"""Run the full PMIP pipeline: ETL → features → regime → train → predict → portfolio."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pmip.pipeline.runner import run_full_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main():
  result = run_full_pipeline()
  logging.info("Pipeline complete: %s", {k: v for k, v in result.items() if k != "train_results"})


if __name__ == "__main__":
  main()
