"""add_notification_emails_to_orgs

Revision ID: d4e8a1f92b35
Revises: c9a1f3e07b28
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4e8a1f92b35'
down_revision: Union[str, None] = 'c9a1f3e07b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("ALTER TABLE organizations ADD COLUMN notification_emails TEXT NOT NULL DEFAULT '[]';")
    else:
        op.execute("ALTER TABLE organizations ADD COLUMN notification_emails JSONB NOT NULL DEFAULT '[]'::jsonb;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        pass
    else:
        op.execute("ALTER TABLE organizations DROP COLUMN notification_emails;")
