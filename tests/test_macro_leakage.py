"""Point-in-time macro data leakage tests.

These tests verify that:
1. Features at date T never use macro values published after T.
2. Revisions released after T are not used.
3. As-of joins filter correctly on release_date.
4. Lag-assumed rows are properly flagged.

Uses synthetic fixtures — no network required.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pmip.db.models import Base, MacroDaily
from pmip.etl.macro import (
    _estimate_release_date,
    get_available_macro_asof,
)
from pmip.features.engineering import (
    _load_macro_wide_pit,
    build_features_asof,
    engineer_cross_asset_features,
)


def _create_test_session():
    """Create a fresh in-memory SQLite session for testing.

    Uses StaticPool to ensure a fresh connection for each test.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _add_macro_with_vintages(session):
    """Add macro data with multiple vintages and known release dates.

    Setup:
      - US10Y observations for 2026-01-01 through 2026-01-10
      - Initial vintage released T+1 for each observation
      - Revision on 2026-01-05 released 2026-01-08 (revised from 4.0 to 4.1)
    """
    obs_dates = [date(2026, 1, i) for i in range(1, 11)]

    for obs_date in obs_dates:
        release = obs_date + timedelta(days=1)
        value = 4.0 + (obs_date.day - 1) * 0.05
        session.add(MacroDaily(
            date=obs_date,
            symbol="US10Y",
            close=Decimal(str(value)),
            source="fred",
            release_date=release,
            vintage="initial",
            lag_assumed=True,
        ))

    session.add(MacroDaily(
        date=date(2026, 1, 5),
        symbol="US10Y",
        close=Decimal("4.25"),
        source="fred",
        release_date=date(2026, 1, 8),
        vintage="2026-01-08",
        lag_assumed=False,
    ))

    session.commit()


def test_asof_join_excludes_future_releases():
    """A feature built for 2026-01-06 must not see the revision released on 2026-01-08."""
    session = _create_test_session()
    _add_macro_with_vintages(session)
    prediction_date = date(2026, 1, 6)

    wide = _load_macro_wide_pit(session, as_of=prediction_date)
    assert not wide.empty

    available_dates = set(d.date() if hasattr(d, 'date') else d for d in wide.index)

    assert date(2026, 1, 5) in available_dates

    jan5_idx = [
        d for d in wide.index
        if (d.date() if hasattr(d, 'date') else d) == date(2026, 1, 5)
    ]
    jan5_value = wide.loc[jan5_idx[0], "US10Y"]
    assert abs(float(jan5_value) - 4.2) < 0.01

    session.close()


def test_asof_join_uses_latest_available_revision():
    """After 2026-01-08, the revision should be visible for 2026-01-05."""
    session = _create_test_session()
    _add_macro_with_vintages(session)
    prediction_date = date(2026, 1, 9)

    wide = _load_macro_wide_pit(session, as_of=prediction_date)

    jan5_idx = [
        d for d in wide.index
        if (d.date() if hasattr(d, 'date') else d) == date(2026, 1, 5)
    ]
    jan5_value = wide.loc[jan5_idx[0], "US10Y"]
    assert abs(float(jan5_value) - 4.25) < 0.01

    session.close()


def test_macro_not_available_before_release():
    """Observations released after the as_of date must be excluded entirely."""
    session = _create_test_session()
    _add_macro_with_vintages(session)
    prediction_date = date(2026, 1, 5)

    wide = _load_macro_wide_pit(session, as_of=prediction_date)
    available_dates = set(d.date() if hasattr(d, 'date') else d for d in wide.index)

    assert date(2026, 1, 5) not in available_dates
    assert date(2026, 1, 4) in available_dates

    session.close()


def test_features_asof_respects_release_dates():
    """Features built as-of a date must only use macro data released by that date."""
    session = _create_test_session()
    _add_macro_with_vintages(session)

    for obs_date in [date(2026, 1, i) for i in range(1, 11)]:
        release = obs_date + timedelta(days=1)
        value = 100 + (obs_date.day - 1) * 0.5
        session.add(MacroDaily(
            date=obs_date,
            symbol="GC=F",
            close=Decimal(str(value)),
            source="yfinance",
            release_date=release,
            vintage="initial",
            lag_assumed=True,
        ))
    session.commit()

    features_early = build_features_asof(session, as_of=date(2026, 1, 6))
    features_late = build_features_asof(session, as_of=date(2026, 1, 10))

    if not features_early.empty:
        early_dates = set(d.date() if hasattr(d, 'date') else d for d in features_early.index)
        assert all(d <= date(2026, 1, 5) for d in early_dates)

    if not features_late.empty:
        late_dates = set(d.date() if hasattr(d, 'date') else d for d in features_late.index)
        assert all(d <= date(2026, 1, 9) for d in late_dates)

    session.close()


def test_publication_lag_estimates_are_conservative():
    """Lag rules should be at least T+1 for daily series."""
    for series_id in ["DGS10", "DGS2", "VIXCLS", "DFII10", "T10YIE"]:
        obs_date = date(2026, 6, 15)
        release_date, lag_assumed = _estimate_release_date(obs_date, series_id, "fred")
        assert release_date > obs_date
        assert lag_assumed is True

    release_date, _ = _estimate_release_date(date(2026, 6, 15), None, "yfinance")
    assert release_date == date(2026, 6, 16)


def test_get_available_macro_asof_filters_correctly():
    """The get_available_macro_asof helper filters to available observations."""
    macro_df = pd.DataFrame([
        {"date": date(2026, 1, 1), "symbol": "US10Y", "close": 4.0,
         "release_date": date(2026, 1, 2), "vintage": "initial"},
        {"date": date(2026, 1, 2), "symbol": "US10Y", "close": 4.1,
         "release_date": date(2026, 1, 3), "vintage": "initial"},
        {"date": date(2026, 1, 3), "symbol": "US10Y", "close": 4.2,
         "release_date": date(2026, 1, 4), "vintage": "initial"},
        {"date": date(2026, 1, 3), "symbol": "US10Y", "close": 4.25,
         "release_date": date(2026, 1, 6), "vintage": "2026-01-06"},
    ])

    available = get_available_macro_asof(macro_df, date(2026, 1, 3))
    assert len(available) == 2
    jan3_rows = available[available["date"] == date(2026, 1, 3)]
    assert len(jan3_rows) == 0

    available = get_available_macro_asof(macro_df, date(2026, 1, 5))
    jan3_rows = available[available["date"] == date(2026, 1, 3)]
    assert len(jan3_rows) == 1
    assert float(jan3_rows.iloc[0]["close"]) == 4.2

    available = get_available_macro_asof(macro_df, date(2026, 1, 7))
    jan3_rows = available[available["date"] == date(2026, 1, 3)]
    assert len(jan3_rows) == 1
    assert float(jan3_rows.iloc[0]["close"]) == 4.25


def test_lag_assumed_flag_distinguishes_vintage_exact():
    """Rows from ALFRED with actual release dates have lag_assumed=False."""
    vintage_exact = MacroDaily(
        date=date(2026, 1, 5),
        symbol="CPI",
        close=Decimal("300.0"),
        source="fred",
        release_date=date(2026, 2, 10),
        vintage="2026-02-10",
        lag_assumed=False,
    )
    assert vintage_exact.lag_assumed is False

    lag_estimated = MacroDaily(
        date=date(2026, 1, 5),
        symbol="US10Y",
        close=Decimal("4.0"),
        source="yfinance",
        release_date=date(2026, 1, 6),
        vintage="initial",
        lag_assumed=True,
    )
    assert lag_estimated.lag_assumed is True


def test_no_future_macro_in_cross_asset_features():
    """Cross-asset features built from wide macro must not peek ahead."""
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    wide = pd.DataFrame({
        "GC=F": np.linspace(100, 110, 30),
        "US10Y_REAL": np.linspace(1.0, 1.5, 30),
        "DX-Y.NYB": np.linspace(104, 106, 30),
        "VIX": np.linspace(15, 20, 30),
    }, index=dates)

    features = engineer_cross_asset_features(wide.iloc[:15])

    if not features.empty and "real_yield" in features.columns:
        last_real_yield = features["real_yield"].dropna().iloc[-1]
        assert last_real_yield <= wide["US10Y_REAL"].iloc[14]


def test_load_macro_to_dataframe_respects_asof():
    """load_macro_to_dataframe with as_of should filter on release_date."""
    from pmip.etl.macro import load_macro_to_dataframe

    session = _create_test_session()
    _add_macro_with_vintages(session)

    df_early = load_macro_to_dataframe(session, as_of=date(2026, 1, 5))
    df_late = load_macro_to_dataframe(session, as_of=date(2026, 1, 10))

    assert len(df_late) >= len(df_early)

    if not df_early.empty:
        early_dates = set(d if isinstance(d, date) else d.date() for d in df_early.index)
        assert date(2026, 1, 5) not in early_dates

    session.close()


def test_vintage_progression_tracked():
    """Multiple vintages for same (date, symbol) should coexist in DB."""
    session = _create_test_session()

    session.add(MacroDaily(
        date=date(2026, 3, 15),
        symbol="CPI",
        close=Decimal("308.417"),
        source="fred",
        release_date=date(2026, 4, 10),
        vintage="2026-04-10",
        lag_assumed=False,
    ))
    session.add(MacroDaily(
        date=date(2026, 3, 15),
        symbol="CPI",
        close=Decimal("308.419"),
        source="fred",
        release_date=date(2026, 5, 10),
        vintage="2026-05-10",
        lag_assumed=False,
    ))
    session.commit()

    rows = session.query(MacroDaily).filter(
        MacroDaily.symbol == "CPI",
        MacroDaily.date == date(2026, 3, 15)
    ).all()
    assert len(rows) == 2

    vintages = {r.vintage for r in rows}
    assert vintages == {"2026-04-10", "2026-05-10"}

    session.close()
