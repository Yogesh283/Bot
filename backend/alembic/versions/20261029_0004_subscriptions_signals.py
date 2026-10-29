"""Add subscriptions and per-user admin signals.

Revision ID: 20261029_0004
Revises: 20261028_0003
Create Date: 2026-10-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261029_0004"
down_revision: Union[str, Sequence[str], None] = "20261028_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("plan", sa.String(40), nullable=False, server_default="demo"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "admin_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("sl_points", sa.Integer(), nullable=False),
        sa.Column("tp_mode", sa.String(20), nullable=False),
        sa.Column("rr", sa.Numeric(8, 2), nullable=True),
        sa.Column("tp_points", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "user_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("admin_signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("retcode", sa.Integer(), nullable=True),
        sa.Column("ticket", sa.BigInteger(), nullable=True),
        sa.Column("reasons", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("signal_id", "user_id", name="uq_user_signals_once"),
    )
    op.execute(
        """
        INSERT INTO subscriptions (user_id, plan, status, expires_at, updated_at)
        SELECT id, 'demo', 'active', now() + interval '365 days', now()
        FROM users
        """
    )


def downgrade() -> None:
    op.drop_table("user_signals")
    op.drop_table("admin_signals")
    op.drop_table("subscriptions")
