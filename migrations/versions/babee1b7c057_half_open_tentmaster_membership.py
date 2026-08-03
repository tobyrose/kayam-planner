"""half open tentmaster membership

Revision ID: babee1b7c057
Revises: 73de560fde26
Create Date: 2026-08-02 09:08:45.947063
"""

from collections.abc import Sequence

from alembic import op

revision: str = "babee1b7c057"
down_revision: str | Sequence[str] | None = "73de560fde26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # end_at now means "first day no longer active" (exclusive), enabling same-day handover
    # between Tentmasters. Previously it meant the last inclusive working day.
    with op.batch_alter_table("tentmaster_memberships") as batch_op:
        batch_op.drop_constraint(op.f("ck_tentmaster_memberships_date_order"), type_="check")
        batch_op.create_check_constraint(
            op.f("ck_tentmaster_memberships_date_order"), "end_at IS NULL OR end_at > start_at"
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("tentmaster_memberships") as batch_op:
        batch_op.drop_constraint(op.f("ck_tentmaster_memberships_date_order"), type_="check")
        batch_op.create_check_constraint(
            op.f("ck_tentmaster_memberships_date_order"), "end_at IS NULL OR end_at >= start_at"
        )
