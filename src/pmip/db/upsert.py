"""Dialect-aware upsert helpers (PostgreSQL + SQLite)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

CONSTRAINT_COLUMNS: dict[str, list[str]] = {
  "uq_macro_daily_date_symbol_vintage": ["date", "symbol", "vintage"],
  "uq_etf_flows_date_ticker": ["date", "ticker"],
  "uq_cb_month_country": ["month", "country"],
  "uq_geopolitical_date": ["date"],
  "uq_miner_ticker_quarter": ["ticker", "quarter_end"],
  "uq_features_daily": ["date", "entity", "feature_name"],
  "uq_regime_date": ["date"],
  "uq_prediction": ["date", "entity", "horizon_days", "model_version"],
  "uq_portfolio_date_rank": ["date", "rank"],
}


# Stay under SQLite's default variable cap (999 on older builds, 32766 on current ones).
_MAX_SQL_VARIABLES = 800


def _chunks(records: list[dict], width: int) -> list[list[dict]]:
  size = max(1, _MAX_SQL_VARIABLES // max(width, 1))
  return [records[i : i + size] for i in range(0, len(records), size)]


def upsert(
  session: Session,
  table: Any,
  records: list[dict],
  constraint: str,
  update_keys: list[str],
) -> None:
  if not records:
    return

  dialect = session.bind.dialect.name if session.bind else "sqlite"
  # Count model columns, not just dict keys. Defaults such as created_at are bound too.
  width = max(len(table.__table__.columns), max(len(row) for row in records))
  batches = _chunks(records, width)

  for batch in batches:
    if dialect == "postgresql":
      from sqlalchemy.dialects.postgresql import insert

      stmt = insert(table).values(batch)
      set_ = {key: getattr(stmt.excluded, key) for key in update_keys}
      stmt = stmt.on_conflict_do_update(constraint=constraint, set_=set_)
    else:
      from sqlalchemy.dialects.sqlite import insert

      index_elements = CONSTRAINT_COLUMNS[constraint]
      stmt = insert(table).values(batch)
      set_ = {key: getattr(stmt.excluded, key) for key in update_keys}
      stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=set_)

    session.execute(stmt)
