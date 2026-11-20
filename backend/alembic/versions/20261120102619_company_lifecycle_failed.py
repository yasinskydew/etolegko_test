"""add company_lifecycle 'failed'

Revision ID: 20261120102619
Revises: 20261120124003
Create Date: 2026-11-20 10:26:19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261120102619"
down_revision: Union[str, None] = "20261120124003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE company_lifecycle ADD VALUE IF NOT EXISTS 'failed'")


def downgrade() -> None:
    op.execute("UPDATE company SET lifecycle = 'creating' WHERE lifecycle = 'failed'")
    op.execute("ALTER TYPE company_lifecycle RENAME TO company_lifecycle_old")
    op.execute("CREATE TYPE company_lifecycle AS ENUM ('creating', 'ready')")
    op.execute(
        "ALTER TABLE company ALTER COLUMN lifecycle TYPE company_lifecycle "
        "USING lifecycle::text::company_lifecycle"
    )
    op.execute("DROP TYPE company_lifecycle_old")
