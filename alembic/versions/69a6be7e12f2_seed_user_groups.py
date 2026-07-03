"""seed user groups

Revision ID: 69a6be7e12f2
Revises: ec5a9ddf8270
Create Date: 2026-07-03 12:45:27.492302

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69a6be7e12f2'
down_revision: Union[str, Sequence[str], None] = 'ec5a9ddf8270'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    user_groups = sa.table(
        "user_groups",
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        user_groups,
        [
            {"name": "USER"},
            {"name": "MODERATOR"},
            {"name": "ADMIN"},
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "DELETE FROM user_groups "
        "WHERE name IN ('USER', 'MODERATOR', 'ADMIN')"
    )

