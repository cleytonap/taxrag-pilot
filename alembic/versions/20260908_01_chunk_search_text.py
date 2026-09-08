"""Separate retrieval text from user-visible citation text.

Revision ID: 20260908_01
Revises: 20260904_01
Create Date: 2026-09-08
"""

import sqlalchemy as sa

from alembic import op

revision = "20260908_01"
down_revision = "20260904_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add derived retrieval text and index the same expression used by the retriever."""
    op.add_column("chunks", sa.Column("search_text", sa.Text(), nullable=True))
    op.execute("UPDATE chunks SET search_text = text")
    op.alter_column("chunks", "search_text", nullable=False)
    op.execute("DROP INDEX ix_chunks_portuguese_search")
    op.execute(
        "CREATE INDEX ix_chunks_portuguese_search "
        "ON chunks USING gin (to_tsvector('portuguese', search_text))"
    )


def downgrade() -> None:
    """Restore the original text-only retrieval representation."""
    op.execute("DROP INDEX ix_chunks_portuguese_search")
    op.execute(
        "CREATE INDEX ix_chunks_portuguese_search "
        "ON chunks USING gin (to_tsvector('portuguese', text))"
    )
    op.drop_column("chunks", "search_text")
