"""ETL pipeline orchestration — plain Python by default, Prefect optional."""

from __future__ import annotations

import logging

from pmip.constants import MACRO_SYMBOLS
from pmip.db.session import get_db_session
from pmip.etl.central_banks import run_central_bank_etl
from pmip.etl.etf_flows import run_etf_flow_etl
from pmip.etl.geopolitical import run_geopolitical_etl
from pmip.etl.macro import run_macro_etl
from pmip.etl.miners import run_miner_etl

logger = logging.getLogger(__name__)


def run_daily_etl(lookback_days: int = 365 * 5, on_progress=None) -> dict:
  """Run full daily ETL without requiring a Prefect server."""
  macro_n = len(MACRO_SYMBOLS)
  post_steps = 4
  etl_total = macro_n + post_steps

  def _note(action: str, item: str, detail: str, done: int) -> None:
    if on_progress is None:
      return
    on_progress(
      "etl",
      status="running",
      action=action,
      item=item,
      detail=detail,
      done=done,
      total=etl_total,
      unit="steps",
    )

  def _macro_progress(stage: str, **kwargs) -> None:
    if on_progress is None:
      return
    # Keep symbol counters on the same ETL progress scale so the bar never jumps backward.
    if kwargs.get("done") is not None:
      kwargs["done"] = min(int(kwargs["done"]), macro_n)
    kwargs["total"] = etl_total
    on_progress(stage, **kwargs)

  with get_db_session() as session:
    _note("Market prices", "Yahoo / FRED", "Downloading futures, ETFs, equities, and yields", 0)
    macro = run_macro_etl(session, lookback_days=lookback_days, on_progress=_macro_progress)

    _note("ETF flows", "GLD / IAU", "Estimating gold-ETF share flows", macro_n)
    etf_flows = run_etf_flow_etl(session, lookback_days=365 * 2)

    _note("Central banks", "Official purchases", "Loading central-bank gold purchases", macro_n + 1)
    central_banks = run_central_bank_etl(session)

    _note("Geopolitical risk", "GPR / conflict", "Refreshing geopolitical risk scores", macro_n + 2)
    geopolitical = run_geopolitical_etl(session, lookback_days=365)

    _note("Miner fundamentals", "Company seed", "Seeding miner companies and quarterly rows", macro_n + 3)
    miners = run_miner_etl(session)

    _note("Market data saved", f"{macro_n} symbols + flows", "Daily ETL finished", etl_total)

    results = {
      "macro": macro,
      "etf_flows": etf_flows,
      "central_banks": central_banks,
      "geopolitical": geopolitical,
      "miners": miners,
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
