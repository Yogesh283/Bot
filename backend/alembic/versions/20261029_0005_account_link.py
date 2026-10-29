"""Record the 100 INR deposit and the broker, VPN, and VPS logins.

Revision ID: 20261029_0005
Revises: 20261029_0004
Create Date: 2026-10-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261029_0005"
down_revision: Union[str, Sequence[str], None] = "20261029_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mt5_credentials", sa.Column("mobile_number", sa.String(20), nullable=True))
    op.add_column("mt5_credentials", sa.Column("vpn_username", sa.String(120), nullable=True))
    op.add_column("mt5_credentials", sa.Column("vpn_password_ciphertext", sa.Text(), nullable=True))
    op.add_column("mt5_credentials", sa.Column("vps_username", sa.String(120), nullable=True))
    op.add_column("mt5_credentials", sa.Column("vps_password_ciphertext", sa.Text(), nullable=True))
    op.add_column("mt5_credentials", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "account_deposits",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("amount_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="confirmed"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("account_deposits")
    op.drop_column("mt5_credentials", "confirmed_at")
    op.drop_column("mt5_credentials", "vps_password_ciphertext")
    op.drop_column("mt5_credentials", "vps_username")
    op.drop_column("mt5_credentials", "vpn_password_ciphertext")
    op.drop_column("mt5_credentials", "vpn_username")
    op.drop_column("mt5_credentials", "mobile_number")
