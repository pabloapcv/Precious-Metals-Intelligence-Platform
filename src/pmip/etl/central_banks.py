"""Phase 2: Central bank gold purchase data."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from pmip.db.models import CentralBankPurchase
from pmip.db.upsert import upsert

logger = logging.getLogger(__name__)

# World Gold Council style monthly data (tonnes purchased)
# In production, scrape/API from WGC; seed with representative structural trend
SEED_CB_DATA: list[dict] = [
  {"month": "2024-01-01", "country": "China", "purchase_tonnes": 15.0},
  {"month": "2024-02-01", "country": "China", "purchase_tonnes": 12.0},
  {"month": "2024-03-01", "country": "China", "purchase_tonnes": 18.0},
  {"month": "2024-01-01", "country": "India", "purchase_tonnes": 8.0},
  {"month": "2024-02-01", "country": "India", "purchase_tonnes": 6.0},
  {"month": "2024-03-01", "country": "India", "purchase_tonnes": 7.0},
  {"month": "2024-01-01", "country": "Turkey", "purchase_tonnes": 10.0},
  {"month": "2024-02-01", "country": "Turkey", "purchase_tonnes": 5.0},
  {"month": "2024-03-01", "country": "Turkey", "purchase_tonnes": 8.0},
  {"month": "2024-01-01", "country": "Russia", "purchase_tonnes": 6.0},
  {"month": "2024-02-01", "country": "Russia", "purchase_tonnes": 4.0},
  {"month": "2024-03-01", "country": "Russia", "purchase_tonnes": 5.0},
  {"month": "2024-01-01", "country": "Kazakhstan", "purchase_tonnes": 3.0},
  {"month": "2024-02-01", "country": "Kazakhstan", "purchase_tonnes": 2.0},
  {"month": "2024-03-01", "country": "Kazakhstan", "purchase_tonnes": 4.0},
  {"month": "2024-01-01", "country": "Singapore", "purchase_tonnes": 2.0},
  {"month": "2024-02-01", "country": "Singapore", "purchase_tonnes": 1.5},
  {"month": "2024-03-01", "country": "Singapore", "purchase_tonnes": 2.5},
  {"month": "2024-01-01", "country": "Poland", "purchase_tonnes": 5.0},
  {"month": "2024-02-01", "country": "Poland", "purchase_tonnes": 4.0},
  {"month": "2024-03-01", "country": "Poland", "purchase_tonnes": 6.0},
]

CB_COUNTRIES = ["China", "India", "Turkey", "Russia", "Kazakhstan", "Singapore", "Poland"]


def _compute_rolling_metrics(records: list[dict]) -> list[dict]:
  """Add rolling 12m and YoY growth to monthly purchase records."""
  import pandas as pd

  df = pd.DataFrame(records)
  df["month"] = pd.to_datetime(df["month"])
  enriched = []
  for country in df["country"].unique():
    cdf = df[df["country"] == country].sort_values("month")
    cdf["rolling_12m_tonnes"] = cdf["purchase_tonnes"].rolling(12, min_periods=1).sum()
    cdf["yoy_growth_pct"] = cdf["purchase_tonnes"].pct_change(12) * 100
    enriched.append(cdf)
  return pd.concat(enriched).to_dict("records")


def upsert_central_bank_data(session: Session, records: list[dict]) -> int:
  enriched = _compute_rolling_metrics(records)
  db_records = []
  for row in enriched:
    db_records.append(
      {
        "month": row["month"].date() if hasattr(row["month"], "date") else date.fromisoformat(str(row["month"])[:10]),
        "country": row["country"],
        "purchase_tonnes": Decimal(str(row["purchase_tonnes"])),
        "rolling_12m_tonnes": Decimal(str(row["rolling_12m_tonnes"])) if pd_notna(row.get("rolling_12m_tonnes")) else None,
        "yoy_growth_pct": Decimal(str(row["yoy_growth_pct"])) if pd_notna(row.get("yoy_growth_pct")) else None,
        "source": "wgc",
      }
    )
  upsert(
    session,
    CentralBankPurchase,
    db_records,
    "uq_cb_month_country",
    ["purchase_tonnes", "rolling_12m_tonnes", "yoy_growth_pct"],
  )
  return len(db_records)


def pd_notna(val) -> bool:
  import pandas as pd
  return val is not None and pd.notna(val)


def run_central_bank_etl(session: Session) -> int:
  """Load central bank purchase data. Extend with WGC API in production."""
  count = upsert_central_bank_data(session, SEED_CB_DATA)
  logger.info("Ingested %d central bank purchase records", count)
  return count
