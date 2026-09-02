"""Create extracted-text, anchor, and chunk tables.

Revision ID: 20260902_01
Revises: 20260901_01
Create Date: 2026-09-02
"""

import sqlalchemy as sa

from alembic import op

revision = "20260902_01"
down_revision = "20260901_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extracted_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("extractor_name", sa.String(length=100), nullable=False),
        sa.Column("extractor_version", sa.String(length=32), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_version_id"),
    )
    op.create_index(
        "ix_extracted_documents_source_version_id",
        "extracted_documents",
        ["source_version_id"],
    )
    op.create_table(
        "source_anchors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("anchor_key", sa.String(length=255), nullable=False),
        sa.Column("display_title", sa.String(length=500), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_version_id", "anchor_key"),
    )
    op.create_index("ix_source_anchors_source_version_id", "source_anchors", ["source_version_id"])
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_anchor_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["source_anchor_id"], ["source_anchors.id"]),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_version_id", "ordinal"),
    )
    op.create_index("ix_chunks_source_version_id", "chunks", ["source_version_id"])
    op.create_index("ix_chunks_source_anchor_id", "chunks", ["source_anchor_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_source_anchor_id", table_name="chunks")
    op.drop_index("ix_chunks_source_version_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_source_anchors_source_version_id", table_name="source_anchors")
    op.drop_table("source_anchors")
    op.drop_index("ix_extracted_documents_source_version_id", table_name="extracted_documents")
    op.drop_table("extracted_documents")
