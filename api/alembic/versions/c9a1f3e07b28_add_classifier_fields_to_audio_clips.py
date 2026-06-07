"""add_classifier_fields_to_audio_clips

Revision ID: c9a1f3e07b28
Revises: 8f3d12b09c47
Create Date: 2026-06-08 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c9a1f3e07b28'
down_revision: Union[str, None] = '8f3d12b09c47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE audio_clips ADD COLUMN classifier_label TEXT;")
    op.execute("ALTER TABLE audio_clips ADD COLUMN classifier_confidence REAL;")
    op.execute("ALTER TABLE audio_clips ADD COLUMN classifier_model_version TEXT;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        pass  # SQLite pre-3.35 cannot drop columns
    else:
        op.execute("ALTER TABLE audio_clips DROP COLUMN classifier_label;")
        op.execute("ALTER TABLE audio_clips DROP COLUMN classifier_confidence;")
        op.execute("ALTER TABLE audio_clips DROP COLUMN classifier_model_version;")
