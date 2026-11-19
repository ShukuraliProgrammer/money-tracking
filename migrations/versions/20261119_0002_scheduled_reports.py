"""Kunlik va haftalik avtomatik hisobotlar uchun ustunlar.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("weekly_report_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("last_weekly_report", sa.String(10), nullable=True))
        batch.add_column(sa.Column("daily_report_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("last_daily_report", sa.String(10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("last_daily_report")
        batch.drop_column("daily_report_enabled")
        batch.drop_column("last_weekly_report")
        batch.drop_column("weekly_report_enabled")
