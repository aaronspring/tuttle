"""add user operating_country

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "operating_country",
            sa.String(),
            nullable=False,
            server_default="Germany",
        ),
    )


def downgrade() -> None:
    op.drop_column("user", "operating_country")
