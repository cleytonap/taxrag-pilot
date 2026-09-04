"""Add page provenance to source anchors.

Revision ID: 20260904_01
Revises: 20260903_01
Create Date: 2026-09-04
"""

import sqlalchemy as sa

from alembic import op

revision = "20260904_01"
down_revision = "20260903_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_anchors", sa.Column("page_start", sa.Integer(), nullable=True))
    op.add_column("source_anchors", sa.Column("page_end", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_anchors", "page_end")
    op.drop_column("source_anchors", "page_start")
