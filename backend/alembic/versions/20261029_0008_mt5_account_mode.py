"""Store whether a saved MT5 login is demo or live.

Revision ID: 20261029_0008
Revises: 20261029_0007
Create Date: 2026-10-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0008"
down_revision: Union[str, Sequence[str], None] = "20261029_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mt5_credentials",
        sa.Column("account_mode", sa.String(length=8), nullable=False, server_default="demo"),
    )


def downgrade() -> None:
    op.drop_column("mt5_credentials", "account_mode")
