"""SQLAlchemy database models for the data warehouse."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ── Phase 2: Macro Data ──────────────────────────────────────────────────────


class MacroDaily(Base):
    """Daily macro and commodity price series."""

    __tablename__ = "macro_daily"
    __table_args__ = (
        UniqueConstraint("date", "symbol", name="uq_macro_daily_date_symbol"),
        Index("ix_macro_daily_symbol_date", "symbol", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    source: Mapped[str] = mapped_column(String(32), default="yfinance")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ETFFlow(Base):
    """Daily and rolling ETF flow metrics for gold ETFs."""

    __tablename__ = "etf_flows"
    __table_args__ = (UniqueConstraint("date", "ticker", name="uq_etf_flows_date_ticker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    aum: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    daily_flow: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    weekly_flow: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    flow_30d_avg: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    flow_60d_avg: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CentralBankPurchase(Base):
    """Monthly central bank gold purchase data."""

    __tablename__ = "central_bank_purchases"
    __table_args__ = (UniqueConstraint("month", "country", name="uq_cb_month_country"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    purchase_tonnes: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    rolling_12m_tonnes: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    yoy_growth_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    source: Mapped[str] = mapped_column(String(64), default="wgc")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GeopoliticalRisk(Base):
    """Daily geopolitical risk index components."""

    __tablename__ = "geopolitical_risk"
    __table_args__ = (UniqueConstraint("date", name="uq_geopolitical_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    gpr_index: Mapped[float] = mapped_column(Float, nullable=False)
    conflict_intensity: Mapped[float | None] = mapped_column(Float)
    sanctions_score: Mapped[float | None] = mapped_column(Float)
    oil_disruption: Mapped[float | None] = mapped_column(Float)
    military_escalation: Mapped[float | None] = mapped_column(Float)
    shipping_disruption: Mapped[float | None] = mapped_column(Float)
    trade_restrictions: Mapped[float | None] = mapped_column(Float)
    election_uncertainty: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="composite")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 3: Miner Database ──────────────────────────────────────────────────


class MinerCompany(Base):
    """Company metadata and classification."""

    __tablename__ = "miner_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)  # senior, mid, junior, royalty
    exchange: Mapped[str | None] = mapped_column(String(16))
    country: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MinerQuarterly(Base):
    """Quarterly fundamental data per miner."""

    __tablename__ = "miner_quarterly"
    __table_args__ = (UniqueConstraint("ticker", "quarter_end", name="uq_miner_ticker_quarter"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    quarter_end: Mapped[date] = mapped_column(Date, nullable=False)
    production_oz: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    aisc_per_oz: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cash_millions: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    debt_millions: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    operating_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    free_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    reserve_life_years: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    mine_locations: Mapped[str | None] = mapped_column(Text)
    political_risk_score: Mapped[float | None] = mapped_column(Float)
    management_guidance: Mapped[str | None] = mapped_column(Text)
    analyst_eps_revision: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 4: Feature Store ─────────────────────────────────────────────────────


class FeatureDaily(Base):
    """Engineered daily features for modeling."""

    __tablename__ = "features_daily"
    __table_args__ = (
        UniqueConstraint("date", "entity", "feature_name", name="uq_features_daily"),
        Index("ix_features_entity_date", "entity", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    entity: Mapped[str] = mapped_column(String(32), nullable=False)  # GLD, GDX, NEM, etc.
    feature_name: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 5: Regime Detection ──────────────────────────────────────────────────


class MarketRegime(Base):
    """Detected market regime assignments."""

    __tablename__ = "market_regimes"
    __table_args__ = (UniqueConstraint("date", name="uq_regime_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    regime_id: Mapped[int] = mapped_column(Integer, nullable=False)
    regime_name: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 6: Predictions ───────────────────────────────────────────────────────


class ModelPrediction(Base):
    """Model predictions for outperformance probability."""

    __tablename__ = "model_predictions"
    __table_args__ = (
        UniqueConstraint("date", "entity", "horizon_days", "model_version", name="uq_prediction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(32), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    prob_outperform_gold: Mapped[float | None] = mapped_column(Float)
    prob_beat_gdx: Mapped[float | None] = mapped_column(Float)
    expected_return: Mapped[float | None] = mapped_column(Float)
    expected_alpha: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    regime_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PortfolioRecommendation(Base):
    """Daily portfolio optimization output."""

    __tablename__ = "portfolio_recommendations"
    __table_args__ = (UniqueConstraint("date", "rank", name="uq_portfolio_date_rank"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    expected_alpha: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(32), default="hrp")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
