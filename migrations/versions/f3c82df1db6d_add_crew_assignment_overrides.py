"""add crew assignment overrides

Revision ID: f3c82df1db6d
Revises: babee1b7c057
Create Date: 2026-08-02 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3c82df1db6d"
down_revision: str | Sequence[str] | None = "babee1b7c057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "crew_assignments",
        sa.Column(
            "override_type",
            sa.Enum("ADD", "EXCLUDE", name="overridetype", native_enum=False, length=10),
            nullable=True,
        ),
    )
    # Every existing named row represented "this person works this phase" — preserve that as an
    # explicit ADD override rather than discarding it.
    op.execute("UPDATE crew_assignments SET override_type = 'ADD' WHERE crew_member_id IS NOT NULL")
    with op.batch_alter_table("crew_assignments") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_crew_assignments_override_type_matches_person"),
            "(crew_member_id IS NOT NULL AND override_type IS NOT NULL) OR "
            "(crew_member_id IS NULL AND override_type IS NULL)",
        )
        batch_op.create_check_constraint(
            op.f("ck_crew_assignments_hourly_override_requires_add"),
            "hourly_cost_override IS NULL OR override_type = 'ADD'",
        )
        batch_op.create_unique_constraint(
            op.f("uq_crew_assignments_job_phase_id"), ["job_phase_id", "crew_member_id"]
        )
        batch_op.drop_constraint(
            op.f("fk_crew_assignments_tentmaster_id_tentmasters"), type_="foreignkey"
        )
        batch_op.drop_index(op.f("ix_crew_assignments_tentmaster_id"))
        batch_op.drop_column("tentmaster_id")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("crew_assignments") as batch_op:
        batch_op.add_column(sa.Column("tentmaster_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            op.f("ix_crew_assignments_tentmaster_id"), ["tentmaster_id"], unique=False
        )
        batch_op.create_foreign_key(
            op.f("fk_crew_assignments_tentmaster_id_tentmasters"),
            "tentmasters",
            ["tentmaster_id"],
            ["id"],
        )
        batch_op.drop_constraint(op.f("uq_crew_assignments_job_phase_id"), type_="unique")
        batch_op.drop_constraint(
            op.f("ck_crew_assignments_hourly_override_requires_add"), type_="check"
        )
        batch_op.drop_constraint(
            op.f("ck_crew_assignments_override_type_matches_person"), type_="check"
        )
    op.drop_column("crew_assignments", "override_type")
