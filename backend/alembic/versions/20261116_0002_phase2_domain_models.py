"""Phase 2 domain models: profiles, DNA, products, history.

Revision ID: 20261116_0002
Revises: 20260316_0001
Create Date: 2026-11-16

Safe additive migration for SQLite — creates new tables only.
Does not drop or alter Phase 1 artefacts.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261116_0002"
down_revision: str | None = "20260316_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("max_budget", sa.Float(), nullable=False),
        sa.Column("min_budget", sa.Float(), nullable=True),
        sa.Column("preferred_categories", sa.JSON(), nullable=False),
        sa.Column("preferred_brands", sa.JSON(), nullable=False),
        sa.Column("disliked_attributes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_product_id", "products", ["product_id"], unique=True)
    op.create_index("ix_products_brand", "products", ["brand"], unique=False)
    op.create_index("ix_products_category", "products", ["category"], unique=False)

    op.create_table(
        "shopper_dna",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("inferred_preferences", sa.JSON(), nullable=False),
        sa.Column("confidence_scores", sa.JSON(), nullable=False),
        sa.Column("preference_sources", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_shopper_dna_user_id", "shopper_dna", ["user_id"], unique=True)

    op.create_table(
        "shopping_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopping_history_user_id", "shopping_history", ["user_id"], unique=False)
    op.create_index("ix_shopping_history_product_id", "shopping_history", ["product_id"], unique=False)
    op.create_index("ix_shopping_history_action", "shopping_history", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shopping_history_action", table_name="shopping_history")
    op.drop_index("ix_shopping_history_product_id", table_name="shopping_history")
    op.drop_index("ix_shopping_history_user_id", table_name="shopping_history")
    op.drop_table("shopping_history")

    op.drop_index("ix_shopper_dna_user_id", table_name="shopper_dna")
    op.drop_table("shopper_dna")

    op.drop_index("ix_products_category", table_name="products")
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_index("ix_products_product_id", table_name="products")
    op.drop_table("products")

    op.drop_table("user_profiles")
