"""ETL pipeline orchestration — plain Python by default, Prefect optional."""

from __future__ import annotations

import logging

from pmip.db.session import get_db_session
from pmip.etl.central_banks import run_central_bank_etl
from pmip.etl.etf_flows import run_etf_flow_etl
from pmip.etl.geopolitical import run_geopolitical_etl
from pmip.etl.macro import run_macro_etl
from pmip.etl.miners import run_miner_etl

logger = logging.getLogger(__name__)


def run_daily_etl(lookback_days: int = 365 * 5) -> dict:
  """Run full daily ETL without requiring a Prefect server."""
  with get_db_session() as session:
    results = {
      "macro": run_macro_etl(session, lookback_days=lookback_days),
      "etf_flows": run_etf_flow_etl(session, lookback_days=365 * 2),
      "central_banks": run_central_bank_etl(session),
      "geopolitical": run_geopolitical_etl(session, lookback_days=365),
      "miners": run_miner_etl(session),
    }
  logger.info("Daily ETL complete: %s", results)
  return results


# Backwards-compatible alias
daily_etl_flow = run_daily_etl


def run_daily_etl_prefect(lookback_days: int = 365 * 5) -> dict:
  """Optional Prefect-wrapped ETL for scheduled production runs."""
  try:
    from prefect import flow, task

    @task(name="ingest_macro", retries=2, retry_delay_seconds=30)
    def ingest_macro(days: int) -> dict:
      with get_db_session() as session:
        return run_macro_etl(session, lookback_days=days)

    @task(name="ingest_etf_flows", retries=2)
    def ingest_etf_flows() -> dict:
      with get_db_session() as session:
        return run_etf_flow_etl(session, lookback_days=365 * 2)

    @task(name="ingest_central_banks")
    def ingest_central_banks() -> int:
      with get_db_session() as session:
        return run_central_bank_etl(session)

    @task(name="ingest_geopolitical", retries=2)
    def ingest_geopolitical() -> int:
      with get_db_session() as session:
        return run_geopolitical_etl(session, lookback_days=365)

    @task(name="ingest_miners")
    def ingest_miners() -> dict:
      with get_db_session() as session:
        return run_miner_etl(session)

    @flow(name="pmip_daily_etl", log_prints=True)
    def _flow(days: int) -> dict:
      return {
        "macro": ingest_macro(days),
        "etf_flows": ingest_etf_flows(),
        "central_banks": ingest_central_banks(),
        "geopolitical": ingest_geopolitical(),
        "miners": ingest_miners(),
      }

    return _flow(lookback_days)
  except Exception as exc:
    logger.warning("Prefect unavailable (%s); running direct ETL", exc)
    return run_daily_etl(lookback_days)


if __name__ == "__main__":
  run_daily_etl()
