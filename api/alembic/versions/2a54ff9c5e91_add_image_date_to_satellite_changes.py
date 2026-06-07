"""add_image_date_to_satellite_changes

Revision ID: 2a54ff9c5e91
Revises: 41ac8eae759c
Create Date: 2026-06-06 01:05:01.318907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a54ff9c5e91'
down_revision: Union[str, None] = '41ac8eae759c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("ALTER TABLE satellite_change_events ADD COLUMN image_date TEXT;")
    else:
        op.execute("ALTER TABLE satellite_change_events ADD COLUMN image_date TIMESTAMPTZ;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        try:
            op.execute("ALTER TABLE satellite_change_events DROP COLUMN image_date;")
        except Exception:
            pass
    else:
        op.execute("ALTER TABLE satellite_change_events DROP COLUMN image_date;")

