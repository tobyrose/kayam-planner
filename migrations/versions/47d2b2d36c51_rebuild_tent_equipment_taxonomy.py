"""rebuild tent equipment taxonomy

Revision ID: 47d2b2d36c51
Revises: f65450c92bb0
Create Date: 2026-08-02 12:47:52.356267
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "47d2b2d36c51"
down_revision: str | Sequence[str] | None = "f65450c92bb0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "equipment_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_equipment_type_id", sa.Integer(), nullable=False),
        sa.Column("child_equipment_type_id", sa.Integer(), nullable=False),
        sa.Column("quantity_per_parent", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "quantity_per_parent > 0", name=op.f("ck_equipment_links_quantity_positive")
        ),
        sa.CheckConstraint(
            "parent_equipment_type_id != child_equipment_type_id",
            name=op.f("ck_equipment_links_no_self_link"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_equipment_type_id"],
            ["equipment_types.id"],
            name=op.f("fk_equipment_links_parent_equipment_type_id_equipment_types"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["child_equipment_type_id"],
            ["equipment_types.id"],
            name=op.f("fk_equipment_links_child_equipment_type_id_equipment_types"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_equipment_links")),
        sa.UniqueConstraint(
            "parent_equipment_type_id",
            "child_equipment_type_id",
            name=op.f("uq_equipment_links_parent_equipment_type_id"),
        ),
    )

    op.create_table(
        "job_tent_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_tent_requirement_id", sa.Integer(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("equipment_type_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["equipment_type_id"],
            ["equipment_types.id"],
            name=op.f("fk_job_tent_sections_equipment_type_id_equipment_types"),
        ),
        sa.ForeignKeyConstraint(
            ["job_tent_requirement_id"],
            ["job_tent_requirements.id"],
            name=op.f("fk_job_tent_sections_job_tent_requirement_id_job_tent_requirements"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_tent_sections")),
        sa.UniqueConstraint(
            "job_tent_requirement_id",
            "sequence_index",
            name=op.f("uq_job_tent_sections_job_tent_requirement_id"),
        ),
    )
    op.create_index(
        op.f("ix_job_tent_sections_job_tent_requirement_id"),
        "job_tent_sections",
        ["job_tent_requirement_id"],
        unique=False,
    )

    op.add_column(
        "equipment_types",
        sa.Column("pack_size", sa.Integer(), server_default="1", nullable=False),
    )
    with op.batch_alter_table("equipment_types") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_equipment_types_pack_size_positive"), "pack_size > 0"
        )

    op.add_column("tent_families", sa.Column("pole_equipment_type_id", sa.Integer(), nullable=True))
    op.add_column(
        "tent_families",
        sa.Column("pole_count_multiplier", sa.Integer(), server_default="2", nullable=False),
    )
    op.add_column(
        "tent_families",
        sa.Column("pole_count_offset", sa.Integer(), server_default="-2", nullable=False),
    )
    op.add_column(
        "tent_families",
        sa.Column(
            "default_build_hours",
            sa.Numeric(precision=8, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "tent_families",
        sa.Column(
            "default_strike_hours",
            sa.Numeric(precision=8, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "tent_families",
        sa.Column("minimum_crew", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "tent_families",
        sa.Column("preferred_crew", sa.Integer(), server_default="0", nullable=False),
    )
    with op.batch_alter_table("tent_families") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_tent_families_pole_multiplier_nonzero"), "pole_count_multiplier != 0"
        )
        batch_op.create_check_constraint(
            op.f("ck_tent_families_build_hours_nonnegative"), "default_build_hours >= 0"
        )
        batch_op.create_check_constraint(
            op.f("ck_tent_families_strike_hours_nonnegative"), "default_strike_hours >= 0"
        )
        batch_op.create_check_constraint(
            op.f("ck_tent_families_minimum_crew_nonnegative"), "minimum_crew >= 0"
        )
        batch_op.create_check_constraint(
            op.f("ck_tent_families_preferred_crew_minimum"), "preferred_crew >= minimum_crew"
        )
        batch_op.create_foreign_key(
            op.f("fk_tent_families_pole_equipment_type_id_equipment_types"),
            "equipment_types",
            ["pole_equipment_type_id"],
            ["id"],
        )

    # --- Data: rebuild the equipment catalog around the real letter-code taxonomy ---
    bind = op.get_bind()
    equipment_types = sa.table(
        "equipment_types",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("category", sa.String),
        sa.column("tent_family_id", sa.Integer),
        sa.column("tracking_mode", sa.String),
        sa.column("pack_size", sa.Integer),
        sa.column("section_capacity_units", sa.Numeric),
        sa.column("pole_capacity_units", sa.Numeric),
        sa.column("ancillary_capacity_units", sa.Numeric),
        sa.column("weight_kg", sa.Numeric),
        sa.column("default_build_stage", sa.String),
        sa.column("active", sa.Boolean),
        sa.column("notes", sa.Text),
    )
    tent_families = sa.table(
        "tent_families",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("pole_equipment_type_id", sa.Integer),
        sa.column("pole_count_multiplier", sa.Integer),
        sa.column("pole_count_offset", sa.Integer),
        sa.column("default_build_hours", sa.Numeric),
        sa.column("default_strike_hours", sa.Numeric),
        sa.column("minimum_crew", sa.Integer),
        sa.column("preferred_crew", sa.Integer),
        sa.column("active", sa.Boolean),
    )
    equipment_links = sa.table(
        "equipment_links",
        sa.column("id", sa.Integer),
        sa.column("parent_equipment_type_id", sa.Integer),
        sa.column("child_equipment_type_id", sa.Integer),
        sa.column("quantity_per_parent", sa.Integer),
        sa.column("notes", sa.Text),
    )
    job_tent_requirements = sa.table(
        "job_tent_requirements",
        sa.column("id", sa.Integer),
        sa.column("tent_configuration_id", sa.Integer),
        sa.column("quantity", sa.Integer),
    )
    job_equipment_requirements = sa.table(
        "job_equipment_requirements",
        sa.column("id", sa.Integer),
        sa.column("equipment_type_id", sa.Integer),
        sa.column("source", sa.String),
    )
    tent_configuration_requirements = sa.table(
        "tent_configuration_requirements",
        sa.column("id", sa.Integer),
        sa.column("tent_configuration_id", sa.Integer),
        sa.column("equipment_type_id", sa.Integer),
        sa.column("quantity", sa.Integer),
    )
    job_tent_sections = sa.table(
        "job_tent_sections",
        sa.column("id", sa.Integer),
        sa.column("job_tent_requirement_id", sa.Integer),
        sa.column("sequence_index", sa.Integer),
        sa.column("equipment_type_id", sa.Integer),
    )

    kayam_id = bind.execute(
        sa.select(tent_families.c.id).where(tent_families.c.name == "Kayam")
    ).scalar()
    if kayam_id is None:
        kayam_id = bind.execute(
            tent_families.insert()
            .values(
                name="Kayam",
                description="DEMONSTRATION DATA — example configurable tent family.",
                pole_count_multiplier=2,
                pole_count_offset=-2,
                active=True,
            )
            .returning(tent_families.c.id)
        ).scalar()

    valhalla_id = bind.execute(
        tent_families.insert()
        .values(
            name="Valhalla",
            description="DEMONSTRATION DATA — pole type/formula not yet configured.",
            pole_count_multiplier=2,
            pole_count_offset=-2,
            active=True,
        )
        .returning(tent_families.c.id)
    ).scalar()

    # Re-point existing rows at their real letter code in place where they exist, so existing
    # EquipmentAsset rows (K1-K3, M1-M5, P1-P20, A1-A2) keep working with no FK remapping needed.
    # A fresh database with no prior seed data has nothing to rename, so each entry falls back to
    # a plain insert.
    all_types = (
        # code, name, category, tent_family_id, tracking_mode, pack_size, stage, old_code
        ("K", "Kayam End", "section", kayam_id, "INDIVIDUAL", 1, "MAIN_SECTIONS", "END"),
        ("M", "Kayam 20M Middle", "section", kayam_id, "INDIVIDUAL", 1, "MAIN_SECTIONS", "MIDDLE"),
        (
            "P",
            "Kayam King Pole (pair)",
            "pole",
            kayam_id,
            "INDIVIDUAL",
            2,
            "POLES_AND_ANCHORS",
            "POLE",
        ),
        (
            "ANCHOR_STILLAGE",
            "Anchor Stillage",
            "linked",
            kayam_id,
            "QUANTITY",
            1,
            "POLES_AND_ANCHORS",
            "ANCHOR_SET",
        ),
        ("m", "Kayam 15M Middle", "section", kayam_id, "INDIVIDUAL", 1, "MAIN_SECTIONS", None),
        ("S", "Siam End", "section", kayam_id, "INDIVIDUAL", 1, "MAIN_SECTIONS", None),
        ("T", "Kayam Triangle", "section", kayam_id, "INDIVIDUAL", 1, "MAIN_SECTIONS", None),
        ("SC", "Kayam Stage Cover", "section", kayam_id, "INDIVIDUAL", 1, "MAIN_SECTIONS", None),
        ("V", "Valhalla Middle", "section", valhalla_id, "INDIVIDUAL", 1, "MAIN_SECTIONS", None),
        (
            "VOE",
            "Valhalla Old End",
            "section",
            valhalla_id,
            "INDIVIDUAL",
            1,
            "MAIN_SECTIONS",
            None,
        ),
        (
            "VNE",
            "Valhalla New End",
            "section",
            valhalla_id,
            "INDIVIDUAL",
            1,
            "MAIN_SECTIONS",
            None,
        ),
        ("X", "X Poles (pair)", "pole", None, "INDIVIDUAL", 2, "POLES_AND_ANCHORS", None),
        (
            "AD",
            "Auger Driver",
            "ancillary",
            None,
            "INDIVIDUAL",
            1,
            "COMPLETION_AND_ANCILLARY",
            None,
        ),
        (
            "SB",
            "Kayam Stake Basher",
            "ancillary",
            kayam_id,
            "INDIVIDUAL",
            1,
            "COMPLETION_AND_ANCILLARY",
            None,
        ),
        (
            "VB",
            "Valhalla Stage Basher",
            "ancillary",
            valhalla_id,
            "INDIVIDUAL",
            1,
            "COMPLETION_AND_ANCILLARY",
            None,
        ),
        (
            "RD",
            "Rock Drill",
            "ancillary",
            None,
            "INDIVIDUAL",
            1,
            "COMPLETION_AND_ANCILLARY",
            None,
        ),
        ("CT", "Crew Tent", "ancillary", None, "INDIVIDUAL", 1, "COMPLETION_AND_ANCILLARY", None),
        ("BALE_RING", "Bale Ring", "linked", kayam_id, "QUANTITY", 1, "MAIN_SECTIONS", None),
        ("SIDE_POLE", "Side Pole", "linked", kayam_id, "QUANTITY", 1, "MAIN_SECTIONS", None),
        ("SIDE_GUY", "Side Guy", "linked", kayam_id, "QUANTITY", 1, "POLES_AND_ANCHORS", None),
        (
            "TIFOR_1_5T",
            "1.5t Tifor",
            "linked",
            kayam_id,
            "QUANTITY",
            1,
            "POLES_AND_ANCHORS",
            None,
        ),
    )
    demo_codes = {"X", "AD", "RD", "CT"}
    type_ids: dict[str, int] = {}
    for code, name, category, family_id, tracking_mode, pack_size, stage, old_code in all_types:
        type_id = None
        if old_code is not None:
            type_id = bind.execute(
                equipment_types.update()
                .where(equipment_types.c.code == old_code)
                .values(
                    code=code,
                    name=name,
                    category=category,
                    tracking_mode=tracking_mode,
                    pack_size=pack_size,
                    default_build_stage=stage,
                )
                .returning(equipment_types.c.id)
            ).scalar()
        if type_id is None:
            type_id = bind.execute(
                equipment_types.insert()
                .values(
                    code=code,
                    name=name,
                    category=category,
                    tent_family_id=family_id,
                    tracking_mode=tracking_mode,
                    pack_size=pack_size,
                    section_capacity_units=0,
                    pole_capacity_units=0,
                    ancillary_capacity_units=0,
                    weight_kg=0,
                    default_build_stage=stage,
                    active=True,
                    notes="DEMONSTRATION DATA — verify before use." if code in demo_codes else None,
                )
                .returning(equipment_types.c.id)
            ).scalar()
        assert type_id is not None
        type_ids[code] = type_id

    # ANCILLARY_KIT never had any EquipmentAsset rows in seeded/known data, so it is dropped
    # outright rather than remapped. Any GENERATED job_equipment_requirements rows referencing it
    # are stale leftovers of the old flat BOM (there is no equivalent under the new model) and
    # would otherwise be orphaned FK references; MANUAL rows are left alone (a planner's decision
    # to keep) even though that leaves a dangling reference for the admin to resolve by hand.
    ancillary_kit_id = bind.execute(
        sa.select(equipment_types.c.id).where(equipment_types.c.code == "ANCILLARY_KIT")
    ).scalar()
    if ancillary_kit_id is not None:
        bind.execute(
            job_equipment_requirements.delete().where(
                job_equipment_requirements.c.equipment_type_id == ancillary_kit_id,
                job_equipment_requirements.c.source == "GENERATED",
            )
        )
    bind.execute(equipment_types.delete().where(equipment_types.c.code == "ANCILLARY_KIT"))

    m_id, p_id = type_ids["M"], type_ids["P"]
    new_type_ids = type_ids

    bind.execute(
        tent_families.update()
        .where(tent_families.c.id == kayam_id)
        .values(
            pole_equipment_type_id=p_id,
            pole_count_multiplier=2,
            pole_count_offset=-2,
            # Carried forward from the old per-size TentConfiguration seed defaults, now a single
            # family-level default (still overridable per job).
            default_build_hours=24,
            default_strike_hours=16,
            minimum_crew=4,
            preferred_crew=6,
        )
    )

    # Only the two ratios the business owner actually confirmed. Side-pole/anchor-stillage
    # quantities under M are deliberately left unconfigured (logged in OPEN_QUESTIONS.md) rather
    # than guessed.
    assert m_id is not None and p_id is not None
    bind.execute(
        equipment_links.insert().values(
            [
                {
                    "parent_equipment_type_id": m_id,
                    "child_equipment_type_id": new_type_ids["BALE_RING"],
                    "quantity_per_parent": 2,
                    "notes": "DEMONSTRATION DATA — confirmed ratio.",
                },
                {
                    "parent_equipment_type_id": p_id,
                    "child_equipment_type_id": new_type_ids["SIDE_GUY"],
                    "quantity_per_parent": 2,
                    "notes": "DEMONSTRATION DATA — confirmed ratio.",
                },
                {
                    "parent_equipment_type_id": p_id,
                    "child_equipment_type_id": new_type_ids["TIFOR_1_5T"],
                    "quantity_per_parent": 2,
                    "notes": "DEMONSTRATION DATA — confirmed ratio.",
                },
            ]
        )
    )

    # --- Data: backfill job_tent_sections from the old named-configuration BOM before it's
    # dropped, so existing jobs keep a correct (if inelegantly-ordered) section sequence. ---
    for job_tent_requirement in bind.execute(
        sa.select(job_tent_requirements.c.id, job_tent_requirements.c.tent_configuration_id)
    ).all():
        section_rows = bind.execute(
            sa.select(
                tent_configuration_requirements.c.equipment_type_id,
                tent_configuration_requirements.c.quantity,
            )
            .select_from(
                tent_configuration_requirements.join(
                    equipment_types,
                    tent_configuration_requirements.c.equipment_type_id == equipment_types.c.id,
                )
            )
            .where(
                tent_configuration_requirements.c.tent_configuration_id
                == job_tent_requirement.tent_configuration_id,
                equipment_types.c.category == "section",
            )
            .order_by(tent_configuration_requirements.c.equipment_type_id)
        ).all()
        sequence_index = 0
        for section_row in section_rows:
            for _ in range(section_row.quantity):
                bind.execute(
                    job_tent_sections.insert().values(
                        job_tent_requirement_id=job_tent_requirement.id,
                        sequence_index=sequence_index,
                        equipment_type_id=section_row.equipment_type_id,
                    )
                )
                sequence_index += 1

    with op.batch_alter_table("job_tent_requirements") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_job_tent_requirements_tent_configuration_id_tent_configurations"),
            type_="foreignkey",
        )
        batch_op.drop_column("tent_configuration_id")

    op.drop_table("tent_configuration_requirements")
    op.drop_table("tent_configurations")


def downgrade() -> None:
    """Downgrade schema.

    Best-effort structural revert only. Section sequences entered under the new model (and any
    equipment types/links beyond the original five) cannot be mapped back to named configurations
    and are discarded — acceptable for this dev-stage database, matching the precedent set by the
    crew-model rework's own downgrade paths.
    """

    op.create_table(
        "tent_configurations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tent_family_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("pole_count", sa.Integer(), nullable=False),
        sa.Column("width_m", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("length_m", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("default_build_hours", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("default_strike_hours", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("minimum_crew", sa.Integer(), nullable=False),
        sa.Column("preferred_crew", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "pole_count > 0", name=op.f("ck_tent_configurations_pole_count_positive")
        ),
        sa.ForeignKeyConstraint(
            ["tent_family_id"],
            ["tent_families.id"],
            name=op.f("fk_tent_configurations_tent_family_id_tent_families"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tent_configurations")),
        sa.UniqueConstraint(
            "tent_family_id", "name", name=op.f("uq_tent_configurations_tent_family_id")
        ),
    )
    op.create_table(
        "tent_configuration_requirements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tent_configuration_id", sa.Integer(), nullable=False),
        sa.Column("equipment_type_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("required_stage", sa.String(length=40), nullable=False),
        sa.Column("individually_assignable", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name=op.f("ck_tent_configuration_requirements_quantity_positive")
        ),
        sa.ForeignKeyConstraint(
            ["equipment_type_id"],
            ["equipment_types.id"],
            name=op.f("fk_tent_configuration_requirements_equipment_type_id_equipment_types"),
        ),
        sa.ForeignKeyConstraint(
            ["tent_configuration_id"],
            ["tent_configurations.id"],
            name=op.f(
                "fk_tent_configuration_requirements_tent_configuration_id_tent_configurations"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tent_configuration_requirements")),
        sa.UniqueConstraint(
            "tent_configuration_id",
            "equipment_type_id",
            "required_stage",
            name=op.f("uq_tent_configuration_requirements_tent_configuration_id"),
        ),
    )

    op.add_column(
        "job_tent_requirements", sa.Column("tent_configuration_id", sa.Integer(), nullable=True)
    )
    with op.batch_alter_table("job_tent_requirements") as batch_op:
        batch_op.create_foreign_key(
            op.f("fk_job_tent_requirements_tent_configuration_id_tent_configurations"),
            "tent_configurations",
            ["tent_configuration_id"],
            ["id"],
        )

    op.drop_index(
        op.f("ix_job_tent_sections_job_tent_requirement_id"), table_name="job_tent_sections"
    )
    op.drop_table("job_tent_sections")
    op.drop_table("equipment_links")

    bind = op.get_bind()
    equipment_types = sa.table(
        "equipment_types", sa.column("id", sa.Integer), sa.column("code", sa.String)
    )
    tent_families = sa.table(
        "tent_families", sa.column("id", sa.Integer), sa.column("name", sa.String)
    )
    bind.execute(
        equipment_types.delete().where(
            equipment_types.c.code.in_(
                [
                    "m",
                    "S",
                    "T",
                    "SC",
                    "V",
                    "VOE",
                    "VNE",
                    "X",
                    "AD",
                    "SB",
                    "VB",
                    "RD",
                    "CT",
                    "BALE_RING",
                    "SIDE_POLE",
                    "SIDE_GUY",
                    "TIFOR_1_5T",
                ]
            )
        )
    )
    bind.execute(
        equipment_types.update()
        .where(equipment_types.c.code == "K")
        .values(code="END", name="End", category="section")
    )
    bind.execute(
        equipment_types.update()
        .where(equipment_types.c.code == "M")
        .values(code="MIDDLE", name="Middle", category="section")
    )
    bind.execute(
        equipment_types.update()
        .where(equipment_types.c.code == "P")
        .values(code="POLE", name="Pole", category="pole", pack_size=1)
    )
    bind.execute(
        equipment_types.update()
        .where(equipment_types.c.code == "ANCHOR_STILLAGE")
        .values(code="ANCHOR_SET", name="Anchor set", category="anchor", tracking_mode="INDIVIDUAL")
    )
    bind.execute(tent_families.delete().where(tent_families.c.name == "Valhalla"))

    with op.batch_alter_table("tent_families") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_tent_families_pole_equipment_type_id_equipment_types"), type_="foreignkey"
        )
        batch_op.drop_constraint(op.f("ck_tent_families_pole_multiplier_nonzero"), type_="check")
        batch_op.drop_constraint(op.f("ck_tent_families_build_hours_nonnegative"), type_="check")
        batch_op.drop_constraint(op.f("ck_tent_families_strike_hours_nonnegative"), type_="check")
        batch_op.drop_constraint(op.f("ck_tent_families_minimum_crew_nonnegative"), type_="check")
        batch_op.drop_constraint(op.f("ck_tent_families_preferred_crew_minimum"), type_="check")
        batch_op.drop_column("preferred_crew")
        batch_op.drop_column("minimum_crew")
        batch_op.drop_column("default_strike_hours")
        batch_op.drop_column("default_build_hours")
        batch_op.drop_column("pole_count_offset")
        batch_op.drop_column("pole_count_multiplier")
        batch_op.drop_column("pole_equipment_type_id")

    with op.batch_alter_table("equipment_types") as batch_op:
        batch_op.drop_constraint(op.f("ck_equipment_types_pack_size_positive"), type_="check")
        batch_op.drop_column("pack_size")
