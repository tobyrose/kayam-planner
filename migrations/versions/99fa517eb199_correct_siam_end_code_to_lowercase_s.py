"""correct siam end code to lowercase s

Revision ID: 99fa517eb199
Revises: e71a563ebf28
Create Date: 2026-08-03 16:25:47.079620
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "99fa517eb199"
down_revision: str | Sequence[str] | None = "e71a563ebf28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Every real reference to Siam End — both the LOADS 26 V8.xlsx reference workbook's own
    "Contents" notation (e.g. "s3-s4-m5-m6-P16-P10") and the real stock list / job CSV provided
    for the Post-V1 reseed — uses lowercase "s", not the uppercase "S" this taxonomy was seeded
    with. Correct it now, before the reseed that depends on it.
    """
    op.get_bind().execute(
        sa.text("UPDATE equipment_types SET code = 's' WHERE code = 'S' AND category = 'section'")
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.get_bind().execute(
        sa.text("UPDATE equipment_types SET code = 'S' WHERE code = 's' AND category = 'section'")
    )
