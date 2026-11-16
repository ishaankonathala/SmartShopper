"""Phase 1 foundation — empty schema baseline.

Revision ID: 20260316_0001
Revises:
Create Date: 2026-03-16

Domain tables are introduced in Phase 2+. This revision establishes
the Alembic history chain against an empty Base.metadata.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260316_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No tables yet — schema arrives with Shopper DNA / catalogue models."""
    # Intentionally empty: Phase 1 only proves migrations + DB connectivity.
    pass


def downgrade() -> None:
    """No-op downgrade for the empty baseline."""
    pass
