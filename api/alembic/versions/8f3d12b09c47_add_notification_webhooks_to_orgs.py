"""add_notification_webhooks_to_orgs

Revision ID: 8f3d12b09c47
Revises: 2a54ff9c5e91
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '8f3d12b09c47'
down_revision: Union[str, None] = '2a54ff9c5e91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("ALTER TABLE organizations ADD COLUMN notification_webhooks TEXT NOT NULL DEFAULT '[]';")
    else:
        op.execute("ALTER TABLE organizations ADD COLUMN notification_webhooks JSONB NOT NULL DEFAULT '[]'::jsonb;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite doesn't support DROP COLUMN before 3.35 — we just leave it
        pass
    else:
        op.execute("ALTER TABLE organizations DROP COLUMN notification_webhooks;")
