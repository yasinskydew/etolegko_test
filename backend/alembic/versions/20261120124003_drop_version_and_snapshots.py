"""drop company.version and stream_offer_snapshot

Revision ID: 20261120124003
Revises: 20261119185515
Create Date: 2026-11-20 12:40:03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261120124003"
down_revision: Union[str, None] = "20261119185515"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("stream_offer_snapshot")
    op.drop_column("company", "version")


def downgrade() -> None:
    op.add_column(
        "company",
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.create_table(
        "stream_offer_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stream_id", sa.BigInteger(), nullable=False),
        sa.Column("offer_id", sa.BigInteger(), nullable=False),
        sa.Column("percent", sa.SmallInteger(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("removed", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "percent >= 0 AND percent <= 100",
            name="stream_offer_snapshot_percent_check",
        ),
        sa.CheckConstraint(
            "position >= 1",
            name="stream_offer_snapshot_position_check",
        ),
        sa.ForeignKeyConstraint(["stream_id"], ["stream.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
