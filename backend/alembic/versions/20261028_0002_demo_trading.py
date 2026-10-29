"""Add demo agent, analysis, and order tables.

Revision ID: 20261028_0002
Revises: 20261028_0001
Create Date: 2026-10-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261028_0002"
down_revision: Union[str, Sequence[str], None] = "20261028_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mt5_connected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("account_login", sa.BigInteger(), nullable=True),
        sa.Column("server_name", sa.String(120), nullable=True),
        sa.Column("environment", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("balance", sa.Numeric(18, 2), nullable=True),
        sa.Column("equity", sa.Numeric(18, 2), nullable=True),
        sa.Column("free_margin", sa.Numeric(18, 2), nullable=True),
        sa.Column("setup_requirement", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", name="uq_trading_agents_user"),
        sa.UniqueConstraint("token_hash", name="uq_trading_agents_token"),
    )
    op.create_table(
        "bot_configs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="stopped"),
        sa.Column("symbol", sa.String(32), nullable=False, server_default="XAUUSD"),
        sa.Column("timeframe", sa.String(8), nullable=False, server_default="M15"),
        sa.Column("fast_period", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("slow_period", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("lot_size", sa.Numeric(12, 4), nullable=False, server_default="0.01"),
        sa.Column("stop_loss_points", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("take_profit_points", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("max_open_positions", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_spread_points", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("max_daily_loss", sa.Numeric(18, 2), nullable=False, server_default="100"),
        sa.Column("demo_trading_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "market_reports",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("spread_points", sa.Numeric(18, 4), nullable=True),
        sa.Column("bid", sa.Numeric(18, 6), nullable=True),
        sa.Column("ask", sa.Numeric(18, 6), nullable=True),
        sa.Column("point", sa.Numeric(18, 8), nullable=True),
        sa.Column("min_volume", sa.Numeric(12, 4), nullable=True),
        sa.Column("max_volume", sa.Numeric(12, 4), nullable=True),
        sa.Column("volume_step", sa.Numeric(12, 4), nullable=True),
        sa.Column("stops_level", sa.Integer(), nullable=True),
        sa.Column("symbol_trade_mode", sa.String(20), nullable=True),
        sa.Column("margin_required", sa.Numeric(18, 2), nullable=True),
        sa.Column("realized_loss_today", sa.Numeric(18, 2), nullable=True),
        sa.Column("candles", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("signal", sa.String(16), nullable=False),
        sa.Column("candle_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fast_ma", sa.Numeric(18, 6), nullable=True),
        sa.Column("slow_ma", sa.Numeric(18, 6), nullable=True),
        sa.Column("data_status", sa.String(16), nullable=False),
        sa.Column("detail", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_analyses_user_id", "analyses", ["user_id"])
    op.create_table(
        "trade_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trading_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("idempotency_key", name="uq_trade_commands_idempotency"),
    )
    op.create_index("ix_trade_commands_user_id", "trade_commands", ["user_id"])
    op.create_table(
        "demo_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trade_commands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("volume", sa.Numeric(12, 4), nullable=False),
        sa.Column("sl", sa.Numeric(18, 6), nullable=True),
        sa.Column("tp", sa.Numeric(18, 6), nullable=True),
        sa.Column("requested_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("retcode", sa.Integer(), nullable=True),
        sa.Column("order_ticket", sa.BigInteger(), nullable=True),
        sa.Column("deal_ticket", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("idempotency_key", name="uq_demo_orders_idempotency"),
    )
    op.create_index("ix_demo_orders_user_id", "demo_orders", ["user_id"])
    op.create_table(
        "reported_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("volume", sa.Numeric(12, 4), nullable=False),
        sa.Column("price_open", sa.Numeric(18, 6), nullable=False),
        sa.Column("sl", sa.Numeric(18, 6), nullable=True),
        sa.Column("tp", sa.Numeric(18, 6), nullable=True),
        sa.Column("profit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "ticket", name="uq_reported_positions_ticket"),
    )
    op.create_index("ix_reported_positions_user_id", "reported_positions", ["user_id"])


def downgrade() -> None:
    op.drop_table("reported_positions")
    op.drop_table("demo_orders")
    op.drop_table("trade_commands")
    op.drop_table("analyses")
    op.drop_table("market_reports")
    op.drop_table("bot_configs")
    op.drop_table("trading_agents")
