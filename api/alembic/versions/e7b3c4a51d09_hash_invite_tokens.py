"""hash_invite_tokens

Revision ID: e7b3c4a51d09
Revises: d4e8a1f92b35
Create Date: 2026-06-11 00:00:00.000000

"""
import hashlib
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e7b3c4a51d09'
down_revision: Union[str, None] = 'd4e8a1f92b35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, token FROM organization_invites")).fetchall()
    for invite_id, token in rows:
        # token_urlsafe(32) values are ~43-char base64url, never 64 lowercase hex,
        # so this guard makes the migration idempotent.
        if token and not re.fullmatch(r"[0-9a-f]{64}", token):
            bind.execute(
                sa.text("UPDATE organization_invites SET token = :token_hash WHERE id = :id"),
                {"token_hash": hashlib.sha256(token.encode()).hexdigest(), "id": invite_id},
            )


def downgrade() -> None:
    # Irreversible by design: plaintext tokens are destroyed.
    pass
