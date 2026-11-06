"""Store the Portuguese search vector; allow full-length anchor titles.

Revision ID: 20261106_01
Revises: 20260908_02
Create Date: 2026-11-06

The V0 baseline showed lexical ranking spends ~0.34 s per query recomputing
to_tsvector over ~1 MB of matched text. A generated column computes it once at write time;
PostgreSQL keeps it in sync with search_text automatically.
"""

from alembic import op

revision = "20261106_01"
down_revision = "20260908_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add a generated tsvector column, move the GIN index onto it, and widen anchor titles."""
    # Extractor v7 keeps full multi-line P&R question titles; the longest is 515 characters.
    op.execute("ALTER TABLE source_anchors ALTER COLUMN display_title TYPE text")
    op.execute(
        "ALTER TABLE chunks ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('portuguese', search_text)) STORED"
    )
    op.execute("DROP INDEX ix_chunks_portuguese_search")
    op.execute("CREATE INDEX ix_chunks_portuguese_search ON chunks USING gin (search_vector)")


def downgrade() -> None:
    """Return to the expression index over search_text."""
    op.execute("ALTER TABLE source_anchors ALTER COLUMN display_title TYPE varchar(500)")
    op.execute("DROP INDEX ix_chunks_portuguese_search")
    op.execute("ALTER TABLE chunks DROP COLUMN search_vector")
    op.execute(
        "CREATE INDEX ix_chunks_portuguese_search "
        "ON chunks USING gin (to_tsvector('portuguese', search_text))"
    )
