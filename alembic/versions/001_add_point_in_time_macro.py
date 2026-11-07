"""Add point-in-time provenance columns to macro_daily.

Revision ID: 001_add_pit_macro
Revises: None
Create Date: 2026-11-06

This migration adds columns to support point-in-time macro data:
  - release_date: When the observation was first published/available.
  - vintage: Revision identifier (ALFRED vintage date or 'initial').
  - lag_assumed: True when release_date is estimated from a lag rule.
  - ingested_at: When this row was ingested.

The unique constraint is updated from (date, symbol) to (date, symbol, vintage)
to support storing multiple vintages of the same observation.
"""
from alembic import op
import sqlalchemy as sa


revision = '001_add_pit_macro'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    op.add_column('macro_daily', sa.Column('release_date', sa.Date(), nullable=True))
    op.add_column('macro_daily', sa.Column('vintage', sa.String(32), server_default='initial', nullable=False))
    op.add_column('macro_daily', sa.Column('lag_assumed', sa.Boolean(), server_default='1', nullable=False))
    op.add_column('macro_daily', sa.Column('ingested_at', sa.DateTime(), nullable=True))

    if dialect == 'postgresql':
        op.execute("""
            UPDATE macro_daily
            SET release_date = date + interval '1 day',
                lag_assumed = true,
                ingested_at = created_at
            WHERE release_date IS NULL
        """)
    else:
        op.execute("""
            UPDATE macro_daily
            SET release_date = date(date, '+1 day'),
                lag_assumed = 1,
                ingested_at = created_at
            WHERE release_date IS NULL
        """)

    if dialect == 'postgresql':
        op.drop_constraint('uq_macro_daily_date_symbol', 'macro_daily', type_='unique')
        op.create_unique_constraint(
            'uq_macro_daily_date_symbol_vintage',
            'macro_daily',
            ['date', 'symbol', 'vintage']
        )
    else:
        op.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_macro_daily_date_symbol_vintage
            ON macro_daily (date, symbol, vintage)
        """)


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        op.drop_constraint('uq_macro_daily_date_symbol_vintage', 'macro_daily', type_='unique')
        op.create_unique_constraint(
            'uq_macro_daily_date_symbol',
            'macro_daily',
            ['date', 'symbol']
        )
    else:
        op.execute('DROP INDEX IF EXISTS uq_macro_daily_date_symbol_vintage')
        op.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_macro_daily_date_symbol
            ON macro_daily (date, symbol)
        """)

    op.drop_column('macro_daily', 'ingested_at')
    op.drop_column('macro_daily', 'lag_assumed')
    op.drop_column('macro_daily', 'vintage')
    op.drop_column('macro_daily', 'release_date')
