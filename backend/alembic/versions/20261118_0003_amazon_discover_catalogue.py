"""Add an isolated Amazon Discover catalogue.

Revision ID: 20261118_0003
Revises: 20261116_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261118_0003"
down_revision: str | None = "20261116_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "amazon_catalogue_products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asin", sa.String(length=10), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("store", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("price_inr", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("rating_count", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("description", sa.JSON(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asin", name="uq_amazon_catalogue_products_asin"),
    )
    op.create_index(
        "ix_amazon_catalogue_products_category",
        "amazon_catalogue_products",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_amazon_catalogue_products_category",
        table_name="amazon_catalogue_products",
    )
    op.drop_table("amazon_catalogue_products")
