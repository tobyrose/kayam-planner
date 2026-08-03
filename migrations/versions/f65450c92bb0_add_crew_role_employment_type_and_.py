"""add crew role employment type and availability windows

Revision ID: f65450c92bb0
Revises: f3c82df1db6d
Create Date: 2026-08-02 10:03:46.505135
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f65450c92bb0"
down_revision: str | Sequence[str] | None = "f3c82df1db6d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "crew_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crew_roles")),
    )
    op.create_index(op.f("ix_crew_roles_name"), "crew_roles", ["name"], unique=True)
    op.create_table(
        "crew_employment_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crew_employment_types")),
    )
    op.create_index(
        op.f("ix_crew_employment_types_name"), "crew_employment_types", ["name"], unique=True
    )
    op.create_table(
        "crew_availability_windows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("crew_member_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.Date(), nullable=False),
        sa.Column("end_at", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "end_at IS NULL OR end_at >= start_at",
            name=op.f("ck_crew_availability_windows_date_order"),
        ),
        sa.ForeignKeyConstraint(
            ["crew_member_id"],
            ["crew_members.id"],
            name=op.f("fk_crew_availability_windows_crew_member_id_crew_members"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crew_availability_windows")),
    )
    op.create_index(
        op.f("ix_crew_availability_windows_crew_member_id"),
        "crew_availability_windows",
        ["crew_member_id"],
        unique=False,
    )

    op.add_column("crew_members", sa.Column("role_id", sa.Integer(), nullable=True))
    op.add_column("crew_members", sa.Column("employment_type_id", sa.Integer(), nullable=True))

    bind = op.get_bind()
    crew_roles = sa.table(
        "crew_roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("is_default", sa.Boolean),
        sa.column("active", sa.Boolean),
    )
    crew_employment_types = sa.table(
        "crew_employment_types",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("is_default", sa.Boolean),
        sa.column("active", sa.Boolean),
    )
    crew_members = sa.table(
        "crew_members",
        sa.column("id", sa.Integer),
        sa.column("role", sa.String),
        sa.column("employment_type", sa.String),
        sa.column("role_id", sa.Integer),
        sa.column("employment_type_id", sa.Integer),
    )

    # Seed the two requested defaults up front, so they exist even with no crew members yet.
    bind.execute(crew_roles.insert().values(name="Monkey", is_default=True, active=True))
    bind.execute(crew_employment_types.insert().values(name="Crew", is_default=True, active=True))

    role_ids: dict[str, int] = {}
    employment_type_ids: dict[str, int] = {}
    rows = bind.execute(
        sa.select(crew_members.c.id, crew_members.c.role, crew_members.c.employment_type)
    ).all()
    for row in rows:
        role_name = row.role
        if role_name not in role_ids:
            existing_role = bind.execute(
                sa.select(crew_roles.c.id).where(crew_roles.c.name == role_name)
            ).scalar()
            if existing_role is None:
                existing_role = bind.execute(
                    crew_roles.insert().values(name=role_name, is_default=False, active=True)
                ).lastrowid
            role_ids[role_name] = existing_role
        employment_type_name = row.employment_type
        if employment_type_name not in employment_type_ids:
            existing_type = bind.execute(
                sa.select(crew_employment_types.c.id).where(
                    crew_employment_types.c.name == employment_type_name
                )
            ).scalar()
            if existing_type is None:
                existing_type = bind.execute(
                    crew_employment_types.insert().values(
                        name=employment_type_name, is_default=False, active=True
                    )
                ).lastrowid
            employment_type_ids[employment_type_name] = existing_type
        bind.execute(
            crew_members.update()
            .where(crew_members.c.id == row.id)
            .values(
                role_id=role_ids[role_name],
                employment_type_id=employment_type_ids[employment_type_name],
            )
        )

    with op.batch_alter_table("crew_members") as batch_op:
        batch_op.alter_column("role_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("employment_type_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_crew_members_role_id_crew_roles"), "crew_roles", ["role_id"], ["id"]
        )
        batch_op.create_foreign_key(
            op.f("fk_crew_members_employment_type_id_crew_employment_types"),
            "crew_employment_types",
            ["employment_type_id"],
            ["id"],
        )
        batch_op.drop_column("role")
        batch_op.drop_column("employment_type")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("crew_members", sa.Column("role", sa.String(length=100), nullable=True))
    op.add_column(
        "crew_members", sa.Column("employment_type", sa.String(length=100), nullable=True)
    )

    bind = op.get_bind()
    crew_roles = sa.table("crew_roles", sa.column("id", sa.Integer), sa.column("name", sa.String))
    crew_employment_types = sa.table(
        "crew_employment_types", sa.column("id", sa.Integer), sa.column("name", sa.String)
    )
    crew_members = sa.table(
        "crew_members",
        sa.column("id", sa.Integer),
        sa.column("role", sa.String),
        sa.column("employment_type", sa.String),
        sa.column("role_id", sa.Integer),
        sa.column("employment_type_id", sa.Integer),
    )
    for row in bind.execute(
        sa.select(crew_members.c.id, crew_members.c.role_id, crew_members.c.employment_type_id)
    ).all():
        role_name = bind.execute(
            sa.select(crew_roles.c.name).where(crew_roles.c.id == row.role_id)
        ).scalar()
        employment_type_name = bind.execute(
            sa.select(crew_employment_types.c.name).where(
                crew_employment_types.c.id == row.employment_type_id
            )
        ).scalar()
        bind.execute(
            crew_members.update()
            .where(crew_members.c.id == row.id)
            .values(role=role_name, employment_type=employment_type_name)
        )

    with op.batch_alter_table("crew_members") as batch_op:
        batch_op.alter_column("role", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column(
            "employment_type", existing_type=sa.String(length=100), nullable=False
        )
        batch_op.drop_constraint(op.f("fk_crew_members_role_id_crew_roles"), type_="foreignkey")
        batch_op.drop_constraint(
            op.f("fk_crew_members_employment_type_id_crew_employment_types"), type_="foreignkey"
        )
        batch_op.drop_column("role_id")
        batch_op.drop_column("employment_type_id")

    op.drop_index(
        op.f("ix_crew_availability_windows_crew_member_id"),
        table_name="crew_availability_windows",
    )
    op.drop_table("crew_availability_windows")
    op.drop_index(op.f("ix_crew_employment_types_name"), table_name="crew_employment_types")
    op.drop_table("crew_employment_types")
    op.drop_index(op.f("ix_crew_roles_name"), table_name="crew_roles")
    op.drop_table("crew_roles")
