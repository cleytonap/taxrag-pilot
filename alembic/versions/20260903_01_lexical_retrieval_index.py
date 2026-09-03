"""Add a GIN index for Portuguese chunk text search.

Revision ID: 20260903_01
Revises: 20260902_01
Create Date: 2026-09-03
"""

from alembic import op

revision = "20260903_01"
down_revision = "20260902_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_chunks_portuguese_search "
        "ON chunks USING gin (to_tsvector('portuguese', text))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_chunks_portuguese_search")
