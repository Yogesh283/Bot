"""Store encrypted MT5 demo logins.

Revision ID: 20261028_0003
Revises: 20261028_0002
Create Date: 2026-10-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261028_0003"
down_revision: Union[str, Sequence[str], None] = "20261028_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mt5_credentials",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("account_login", sa.BigInteger(), nullable=False),
        sa.Column("server_name", sa.String(120), nullable=False),
        sa.Column("password_ciphertext", sa.Text(), nullable=False),
        sa.Column("terminal_path", sa.String(260), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("mt5_credentials")
