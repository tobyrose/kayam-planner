from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.administration import (
    BuildStage,
    CrewEmploymentType,
    CrewMember,
    CrewRole,
    EquipmentAsset,
    EquipmentLink,
    EquipmentType,
    Haulier,
    Location,
    LocationType,
    Lorry,
    LorryType,
    OwnershipType,
    TentFamily,
    Tentmaster,
    TentmasterMembership,
    TrackingMode,
    Van,
)
from app.models.costing import CostCategory, LoadCostAllocation, SupplierInvoice
from app.models.crew_movements import (
    CrewJourneyLeg,
    CrewMovement,
    CrewMovementPassenger,
    JourneyMode,
)
from app.models.equipment_planning import AllocationStrength, EquipmentAssignment
from app.models.jobs import (
    CommercialStatus,
    Job,
    PhaseType,
    PlanningStatus,
    RecordSource,
)
from app.models.logistics import EquipmentMovement, Load, LoadItem, LoadStatus, MovementStatus
from app.services.jobs import JobService

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_or_create(
    session: Session,
    model: type[Any],
    lookup: dict[str, Any],
    defaults: dict[str, Any] | None = None,
) -> tuple[Any, bool]:
    conditions = [getattr(model, key) == value for key, value in lookup.items()]
    record = session.scalar(select(model).where(*conditions))
    if record is not None:
        return record, False
    record = model(**lookup, **(defaults or {}))
    session.add(record)
    session.flush()
    return record, True


# Real per-section linked-parts quantities, transcribed verbatim from the owner-supplied
# reference/kay.parts.csv stock sheet (2026-08-03) — one row per part, one column per Kayam-family
# section code (K, m, M, T, SC, s, P, X). Blank/zero cells in the source mean "not applicable" and
# are simply omitted here. `SIDE_POLE`/`BALE_RING` reuse the pre-existing placeholder codes from
# `equipment_definitions` above (their names/categories are untouched by `get_or_create` once they
# already exist) since the CSV's "Sidepole"/"Balerings" rows are unambiguously the same items —
# `Balerings` even confirms the M=2 ratio already configured. Every other row is a genuinely new
# linked-equipment type. `default_build_stage` groups pole/rigging hardware under
# `POLES_AND_ANCHORS` and section-cladding hardware under `MAIN_SECTIONS`, mirroring the
# convention already used for `SIDE_POLE`/`SIDE_GUY`/`BALE_RING`/`ANCHOR_STILLAGE` — inferred from
# what each part actually is, not stated in the CSV itself.
LINKED_PARTS_MATRIX: tuple[tuple[str, str, BuildStage, dict[str, int]], ...] = (
    (
        "STANDARD_GUYS",
        "Standard Guys",
        BuildStage.POLES_AND_ANCHORS,
        {"K": 1, "m": 1, "M": 1, "T": 1, "s": 1, "P": 3, "X": 3},
    ),
    (
        "TIFOR_1_6T",
        "1.6 Ton Tirfor",
        BuildStage.POLES_AND_ANCHORS,
        {"K": 1, "m": 1, "M": 1, "T": 1, "s": 1, "P": 3, "X": 3},
    ),
    (
        "TIFOR_3_2T",
        "3.2 Ton Tirfor",
        BuildStage.POLES_AND_ANCHORS,
        {"K": 1, "m": 1, "M": 1, "T": 1, "s": 1, "P": 3, "X": 3},
    ),
    (
        "POLE_LIFT_CABLE_66M",
        "66M Pole lift Cable",
        BuildStage.POLES_AND_ANCHORS,
        {"K": 1, "m": 1, "M": 1, "T": 1, "s": 1, "P": 3, "X": 3},
    ),
    (
        "BALERING_CABLE_18M",
        "18M Balering Cable",
        BuildStage.POLES_AND_ANCHORS,
        {"K": 1, "m": 1, "M": 1, "T": 1, "s": 1, "P": 3, "X": 3},
    ),
    (
        "STRETCHER_12_1M_WHITE",
        "12.1M Stretcher (white)",
        BuildStage.POLES_AND_ANCHORS,
        {"K": 2, "m": 2, "M": 2, "T": 4, "SC": 2, "s": 2, "P": 2, "X": 2},
    ),
    ("GUY_EXTN_BLUE", "Guy extns (Blue)", BuildStage.POLES_AND_ANCHORS, {"K": 2}),
    ("BALERING_CABLE_RED", "Balering cables (Red)", BuildStage.POLES_AND_ANCHORS, {"P": 4, "X": 4}),
    ("BALERING_CABLE_EXTN_1M", "Balering cable extns 1M", BuildStage.POLES_AND_ANCHORS, {"X": 4}),
    (
        "RADIAL_GUY",
        "Radial Guys (Black rope or red sleeve)",
        BuildStage.POLES_AND_ANCHORS,
        {"T": 6},
    ),
    (
        "STRETCHER_14_75M_GREEN",
        "14.75M Stretchers (Green)",
        BuildStage.POLES_AND_ANCHORS,
        {"P": 1, "X": 1},
    ),
    (
        "WALL_PANEL_M",
        "Walls (M)",
        BuildStage.MAIN_SECTIONS,
        {"K": 75, "m": 30, "M": 40, "s": 55},
    ),
    (
        "STAKE",
        "Stakes",
        BuildStage.MAIN_SECTIONS,
        {"K": 60, "m": 25, "M": 30, "T": 25, "SC": 20, "s": 40},
    ),
    (
        "SIDE_POLE",
        "Side Pole",
        BuildStage.MAIN_SECTIONS,
        {"K": 30, "m": 12, "M": 16, "T": 3, "SC": 1, "s": 18},
    ),
    (
        "RATCHET",
        "Ratchets",
        BuildStage.MAIN_SECTIONS,
        {"K": 50, "m": 20, "M": 25, "T": 20, "SC": 10, "s": 35},
    ),
    (
        "BALE_RING",
        "Bale Ring",
        BuildStage.MAIN_SECTIONS,
        {"K": 1, "m": 2, "M": 2, "T": 3, "SC": 1, "s": 1},
    ),
    (
        "CAP",
        "Caps",
        BuildStage.MAIN_SECTIONS,
        {"K": 1, "m": 2, "M": 2, "T": 3, "SC": 1, "s": 1, "X": 2},
    ),
    ("X_BASE_PLATE", "X Base Plates", BuildStage.POLES_AND_ANCHORS, {"X": 2}),
    ("X_HINGE", "X Hinges", BuildStage.POLES_AND_ANCHORS, {"X": 2}),
    ("P_BASE_PLATE", "P Base Plate", BuildStage.POLES_AND_ANCHORS, {"P": 2}),
    ("P_HINGE", "P Hinges", BuildStage.POLES_AND_ANCHORS, {"P": 2}),
    ("BASEPLATE_STAKE", "Baseplate Stakes", BuildStage.POLES_AND_ANCHORS, {"P": 8, "X": 8}),
    ("FLAG_AND_POLE", "Flag & Pole", BuildStage.COMPLETION_AND_ANCILLARY, {"P": 2, "X": 2}),
    ("SC_RIGGING_BOX", "Stage Cover Rigging box", BuildStage.COMPLETION_AND_ANCILLARY, {"SC": 1}),
)


def _ensure_linked_parts(session: Session, equipment_types: dict[str, EquipmentType]) -> int:
    created = 0
    kayam_family_id = equipment_types["K"].tent_family_id
    for code, name, stage, quantities in LINKED_PARTS_MATRIX:
        part_type, was_created = get_or_create(
            session,
            EquipmentType,
            {"code": code},
            {
                "name": name,
                "category": "linked",
                "tent_family_id": kayam_family_id,
                "tracking_mode": TrackingMode.QUANTITY,
                "pack_size": 1,
                "default_build_stage": stage,
                "notes": "Source: reference/kay.parts.csv (owner-supplied, 2026-08-03).",
            },
        )
        equipment_types.setdefault(code, part_type)
        created += was_created
        for parent_code, quantity_per_parent in quantities.items():
            _, link_created = get_or_create(
                session,
                EquipmentLink,
                {
                    "parent_equipment_type_id": equipment_types[parent_code].id,
                    "child_equipment_type_id": part_type.id,
                },
                {
                    "quantity_per_parent": quantity_per_parent,
                    "notes": "Source: reference/kay.parts.csv (owner-supplied, 2026-08-03).",
                },
            )
            created += link_created
    return created


# Lorry loading points per equipment type (owner Q042). Stored on
# EquipmentType.section_capacity_units so load capacity % uses the same field as Curtain 6 /
# Flat 7.2 on LorryType.section_capacity_units. SC and Valhalla have no confirmed points yet.
LOADING_POINTS: dict[str, Decimal] = {
    "K": Decimal("1.2"),
    "m": Decimal("1"),
    "M": Decimal("1"),
    "T": Decimal("1"),
    "s": Decimal("1.2"),
    "P": Decimal("1.2"),
    "X": Decimal("1.4"),
}


def _ensure_loading_points(session: Session) -> int:
    """Apply Q042 points onto equipment types (idempotent updates)."""
    updated = 0
    for code, points in LOADING_POINTS.items():
        equipment_type = session.scalar(select(EquipmentType).where(EquipmentType.code == code))
        if equipment_type is None:
            continue
        if equipment_type.section_capacity_units != points:
            equipment_type.section_capacity_units = points
            updated += 1
    if updated:
        session.flush()
    return updated


def seed_development_data(session: Session, *, include_operational_demo: bool = False) -> int:
    """Insert idempotent, explicitly labelled demonstration reference data."""

    created = 0
    oxford, was_created = get_or_create(
        session,
        Location,
        {"name": "Oxford Yard"},
        {
            "location_type": LocationType.YARD,
            "country_code": "GB",
            "timezone": "Europe/London",
            "access_notes": "DEMONSTRATION DATA — replace with verified operational details.",
            "default_unload_duration_minutes": 60,
        },
    )
    created += was_created

    kayam, was_created = get_or_create(
        session,
        TentFamily,
        {"name": "Kayam"},
        {"description": "DEMONSTRATION DATA — example configurable tent family."},
    )
    created += was_created
    valhalla, was_created = get_or_create(
        session,
        TentFamily,
        {"name": "Valhalla"},
        {"description": "DEMONSTRATION DATA — pole type/formula not yet configured."},
    )
    created += was_created

    # code, name, category, tent_family, tracking_mode, pack_size, stage
    equipment_definitions = (
        ("K", "Kayam End", "section", kayam, TrackingMode.INDIVIDUAL, 1, BuildStage.MAIN_SECTIONS),
        (
            "M",
            "Kayam 20M Middle",
            "section",
            kayam,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.MAIN_SECTIONS,
        ),
        (
            "m",
            "Kayam 15M Middle",
            "section",
            kayam,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.MAIN_SECTIONS,
        ),
        ("s", "Siam End", "section", kayam, TrackingMode.INDIVIDUAL, 1, BuildStage.MAIN_SECTIONS),
        (
            "T",
            "Kayam Triangle",
            "section",
            kayam,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.MAIN_SECTIONS,
        ),
        (
            "SC",
            "Kayam Stage Cover",
            "section",
            kayam,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.MAIN_SECTIONS,
        ),
        (
            "V",
            "Valhalla Middle",
            "section",
            valhalla,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.MAIN_SECTIONS,
        ),
        (
            "VOE",
            "Valhalla Old End",
            "section",
            valhalla,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.MAIN_SECTIONS,
        ),
        (
            "VNE",
            "Valhalla New End",
            "section",
            valhalla,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.MAIN_SECTIONS,
        ),
        (
            "P",
            "Kayam King Pole (pair)",
            "pole",
            kayam,
            TrackingMode.INDIVIDUAL,
            2,
            BuildStage.POLES_AND_ANCHORS,
        ),
        (
            "X",
            "X Poles (pair)",
            "pole",
            None,
            TrackingMode.INDIVIDUAL,
            2,
            BuildStage.POLES_AND_ANCHORS,
        ),
        (
            "AD",
            "Auger Driver",
            "ancillary",
            None,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.COMPLETION_AND_ANCILLARY,
        ),
        (
            "SB",
            "Kayam Stake Basher",
            "ancillary",
            kayam,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.COMPLETION_AND_ANCILLARY,
        ),
        (
            "VB",
            "Valhalla Stage Basher",
            "ancillary",
            valhalla,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.COMPLETION_AND_ANCILLARY,
        ),
        (
            "RD",
            "Rock Drill",
            "ancillary",
            None,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.COMPLETION_AND_ANCILLARY,
        ),
        (
            "CT",
            "Crew Tent",
            "ancillary",
            None,
            TrackingMode.INDIVIDUAL,
            1,
            BuildStage.COMPLETION_AND_ANCILLARY,
        ),
        (
            "ANCHOR_STILLAGE",
            "Anchor Stillage",
            "linked",
            kayam,
            TrackingMode.QUANTITY,
            1,
            BuildStage.POLES_AND_ANCHORS,
        ),
        (
            "BALE_RING",
            "Bale Ring",
            "linked",
            kayam,
            TrackingMode.QUANTITY,
            1,
            BuildStage.MAIN_SECTIONS,
        ),
        (
            "SIDE_POLE",
            "Side Pole",
            "linked",
            kayam,
            TrackingMode.QUANTITY,
            1,
            BuildStage.MAIN_SECTIONS,
        ),
        (
            "SIDE_GUY",
            "Side Guy",
            "linked",
            kayam,
            TrackingMode.QUANTITY,
            1,
            BuildStage.POLES_AND_ANCHORS,
        ),
        (
            "TIFOR_1_5T",
            "1.5t Tifor",
            "linked",
            kayam,
            TrackingMode.QUANTITY,
            1,
            BuildStage.POLES_AND_ANCHORS,
        ),
    )
    equipment_types: dict[str, EquipmentType] = {}
    for code, name, category, family, tracking_mode, pack_size, stage in equipment_definitions:
        is_demo_placeholder = code in {"X", "AD", "RD", "CT"}
        equipment_type, was_created = get_or_create(
            session,
            EquipmentType,
            {"code": code},
            {
                "name": name,
                "category": category,
                "tent_family_id": family.id if family else None,
                "tracking_mode": tracking_mode,
                "pack_size": pack_size,
                "default_build_stage": stage,
                "notes": "DEMONSTRATION DATA — verify before use."
                if is_demo_placeholder
                else None,
            },
        )
        equipment_types[code] = equipment_type
        created += was_created

    if kayam.pole_equipment_type_id is None:
        kayam.pole_equipment_type_id = equipment_types["P"].id
        kayam.pole_count_multiplier = 2
        kayam.pole_count_offset = -2
        kayam.default_build_hours = Decimal("24")
        kayam.default_strike_hours = Decimal("16")
        kayam.minimum_crew = 4
        kayam.preferred_crew = 6

    # Only the two ratios confirmed by the business owner at the time. Superseded below by the
    # full real parts matrix from reference/kay.parts.csv — kept here for history/idempotency
    # (SIDE_GUY/TIFOR_1_5T are placeholder names/quantities the owner has since flagged as
    # probably redundant with STANDARD_GUYS/TIFOR_1_6T/TIFOR_3_2T below; not merged automatically,
    # see OPEN_QUESTIONS.md).
    link_definitions = (
        ("M", "BALE_RING", 2),
        ("P", "SIDE_GUY", 2),
        ("P", "TIFOR_1_5T", 2),
    )
    for parent_code, child_code, quantity_per_parent in link_definitions:
        _, was_created = get_or_create(
            session,
            EquipmentLink,
            {
                "parent_equipment_type_id": equipment_types[parent_code].id,
                "child_equipment_type_id": equipment_types[child_code].id,
            },
            {
                "quantity_per_parent": quantity_per_parent,
                "notes": "DEMONSTRATION DATA — confirmed ratio.",
            },
        )
        created += was_created

    created += _ensure_linked_parts(session, equipment_types)
    created += _ensure_loading_points(session)

    asset_codes = ["K1", "K2", "K3"] + [f"M{number}" for number in range(1, 6)]
    asset_codes += [f"P{number}" for number in range(1, 21)] + ["A1", "A2"]
    asset_types = {
        "K": equipment_types["K"],
        "M": equipment_types["M"],
        "P": equipment_types["P"],
        "A": equipment_types["ANCHOR_STILLAGE"],
    }
    for asset_code in asset_codes:
        _, was_created = get_or_create(
            session,
            EquipmentAsset,
            {"asset_code": asset_code},
            {
                "equipment_type_id": asset_types[asset_code[0]].id,
                "initial_location_id": oxford.id,
                "current_status": "available",
                "notes": "DEMONSTRATION DATA",
            },
        )
        created += was_created

    default_role, was_created = get_or_create(
        session, CrewRole, {"name": "Monkey"}, {"is_default": True}
    )
    created += was_created
    default_employment_type, was_created = get_or_create(
        session, CrewEmploymentType, {"name": "Crew"}, {"is_default": True}
    )
    created += was_created

    crew_members: list[CrewMember] = []
    for number in range(1, 5):
        crew_member, was_created = get_or_create(
            session,
            CrewMember,
            {"name": f"Demo Crew {number}"},
            {
                "role_id": default_role.id,
                "employment_type_id": default_employment_type.id,
                "home_location_id": oxford.id,
                "notes": "DEMONSTRATION DATA — not a real person.",
            },
        )
        crew_members.append(crew_member)
        created += was_created

    van, was_created = get_or_create(
        session,
        Van,
        {"registration_or_name": "DEMO-VAN-1"},
        {
            "passenger_capacity": 9,
            "cargo_capacity_units": Decimal("0"),
            "home_location_id": oxford.id,
            "ownership_type": OwnershipType.OWNED,
            "cost_per_km": Decimal("0"),
            "notes": "DEMONSTRATION DATA — capacities and costs are placeholders.",
        },
    )
    created += was_created

    tentmasters: list[Tentmaster] = []
    for index, name in enumerate(("Max/Martin", "Ross", "Jesse", "Marley")):
        tentmaster, was_created = get_or_create(
            session,
            Tentmaster,
            {"name": name},
            {
                "lead_crew_member_id": crew_members[index].id,
                "home_location_id": oxford.id,
                "default_van_id": van.id if index == 0 else None,
                "notes": "DEMONSTRATION DATA — verify team definitions.",
            },
        )
        tentmasters.append(tentmaster)
        created += was_created
        _, was_created = get_or_create(
            session,
            TentmasterMembership,
            {
                "tentmaster_id": tentmaster.id,
                "crew_member_id": crew_members[index].id,
                "start_at": date(2026, 1, 1),
            },
            {"is_default": True, "notes": "DEMONSTRATION DATA"},
        )
        created += was_created

    # Operational lorry types from owner capacity data (Q042): Curtain 6 pts, Flat 7.2 pts.
    # section_capacity_units holds the points budget until a dedicated points model lands.
    # "Standard artic" is legacy demo only — deactivated if present, not offered on forms.
    lorry_type = None
    for name, section_points, notes in (
        (
            "Curtain",
            Decimal("6"),
            "Curtainsider — 6 loading points (Q042). Prefer Flat when either will do.",
        ),
        (
            "Flat",
            Decimal("7.2"),
            "Flatbed — 7.2 loading points (Q042). Preferred over Curtain when either will do.",
        ),
    ):
        item, was_created = get_or_create(
            session,
            LorryType,
            {"name": name},
            {
                "section_capacity_units": section_points,
                "pole_capacity_units": Decimal("0"),
                "ancillary_capacity_units": Decimal("0"),
                "payload_kg": Decimal("0"),
                "passenger_capacity": 0,
                "default_cost_per_km": Decimal("0"),
                "minimum_load_cost": Decimal("0"),
                "notes": notes,
                "active": True,
            },
        )
        created += was_created
        if name == "Flat":
            lorry_type = item
    legacy = session.scalar(select(LorryType).where(LorryType.name == "Standard artic"))
    if legacy is not None and legacy.active:
        legacy.active = False
        created += 1
    assert lorry_type is not None
    haulier, was_created = get_or_create(
        session,
        Haulier,
        {"name": "Demo Haulier"},
        {"notes": "DEMONSTRATION DATA — not a real supplier."},
    )
    created += was_created
    lorry, was_created = get_or_create(
        session,
        Lorry,
        {"registration_or_name": "DEMO-LORRY-1"},
        {
            "lorry_type_id": lorry_type.id,
            "haulier_id": haulier.id,
            "ownership_type": OwnershipType.SUPPLIER,
            "home_location_id": oxford.id,
            "notes": "DEMONSTRATION DATA — not a real vehicle.",
        },
    )
    created += was_created

    demo_sites: dict[str, Location] = {}
    for name in ("Roskilde Demo Site", "Scotland Demo Site", "UK Demo Event Site"):
        site, was_created = get_or_create(
            session,
            Location,
            {"name": name},
            {
                "location_type": LocationType.SITE,
                "country_code": "GB" if name != "Roskilde Demo Site" else "DK",
                "timezone": "Europe/London"
                if name != "Roskilde Demo Site"
                else "Europe/Copenhagen",
                "access_notes": "DEMONSTRATION DATA — not a verified operational location.",
            },
        )
        demo_sites[name] = site
        created += was_created

    london = ZoneInfo("Europe/London")
    demo_jobs = (
        (
            "DEMO-ROS-26",
            "Roskilde Demonstration",
            demo_sites["Roskilde Demo Site"],
            datetime(2026, 6, 18, 8, tzinfo=london),
            datetime(2026, 6, 22, 20, tzinfo=london),
            datetime(2026, 6, 30, 8, tzinfo=london),
            "K-M-M-M-M-K",  # 6 sections -> 10 poles (2 ends, 4 middles)
            CommercialStatus.CONFIRMED,
            PlanningStatus.PLANNER_APPROVED,
        ),
        (
            "DEMO-SCO-26",
            "Scotland Demonstration",
            demo_sites["Scotland Demo Site"],
            datetime(2026, 7, 10, 8, tzinfo=london),
            datetime(2026, 7, 12, 20, tzinfo=london),
            datetime(2026, 7, 18, 8, tzinfo=london),
            "K-M-M-K",  # 4 sections -> 6 poles (2 ends, 2 middles)
            CommercialStatus.QUOTED,
            PlanningStatus.PROVISIONAL_PLAN,
        ),
        (
            "DEMO-UK-26",
            "UK Event Demonstration",
            demo_sites["UK Demo Event Site"],
            datetime(2026, 8, 10, 8, tzinfo=london),
            datetime(2026, 8, 12, 20, tzinfo=london),
            datetime(2026, 8, 17, 8, tzinfo=london),
            "K-M-K",  # 3 sections -> 4 poles (2 ends, 1 middle)
            CommercialStatus.ENQUIRY,
            PlanningStatus.NOT_PLANNED,
        ),
    )
    job_service = JobService(session)
    jobs_by_code: dict[str, Job] = {}
    for code, name, site, access_at, up_at, strike_at, sequence, commercial, planning in demo_jobs:
        job, was_created = get_or_create(
            session,
            Job,
            {"job_code": code},
            {
                "name": name,
                "customer_name": "Demonstration customer",
                "location_id": site.id,
                "commercial_status": commercial,
                "planning_status": planning,
                "contract_revenue": Decimal("0"),
                "currency": "GBP",
                "site_access_at": access_at,
                "site_clear_by": strike_at + timedelta(days=2),
                "operational_notes": "DEMONSTRATION DATA — not operational work.",
            },
        )
        jobs_by_code[code] = job
        if "DEMONSTRATION DATA" in (job.operational_notes or ""):
            job.contract_revenue = {
                "DEMO-ROS-26": Decimal("50000"),
                "DEMO-SCO-26": Decimal("28000"),
                "DEMO-UK-26": Decimal("18000"),
            }[code]
        created += was_created
        if not job.tent_requirements:
            job_service.add_tent_requirement(
                job.id,
                {
                    "sequence": sequence,
                    "quantity": 1,
                    "custom_name": None,
                    "contracted_up_at": up_at,
                    "contracted_down_at": strike_at,
                    "notes": "DEMONSTRATION DATA",
                },
            )
            created += 1
        session.expire(job, ["tent_requirements", "equipment_requirements", "phases"])

    if include_operational_demo:
        roskilde = jobs_by_code["DEMO-ROS-26"]
        roskilde_build = next(
            phase for phase in roskilde.phases if phase.phase_type == PhaseType.BUILD
        )
        if roskilde_build.tentmaster_id is None:
            roskilde_build.tentmaster_id = tentmasters[0].id
            created += 1
        # Demo Crew 1 is Max/Martin's own roster member (see the membership loop above) and is
        # derived onto this phase automatically. This local crew booking demonstrates the other
        # source of headcount: anonymous local/hired crew booked onto the job over a date range,
        # joining whichever phase(s) are active over that window.
        if not roskilde.local_crew_bookings:
            job_service.add_local_crew_booking(
                roskilde.id,
                {
                    "headcount": 4,
                    "start_at": roskilde_build.start_at,
                    "end_at": roskilde_build.end_at,
                    "notes": "DEMONSTRATION DATA — local crew booked for the build",
                },
            )
            created += 1

        end_requirement = next(
            requirement
            for requirement in roskilde.equipment_requirements
            if requirement.equipment_type.code == "K"
        )
        demo_assets = session.scalars(
            select(EquipmentAsset).where(EquipmentAsset.asset_code.in_(["K1", "K2"]))
        ).all()
        for asset in demo_assets:
            _, was_created = get_or_create(
                session,
                EquipmentAssignment,
                {
                    "job_equipment_requirement_id": end_requirement.id,
                    "equipment_asset_id": asset.id,
                },
                {
                    "start_at": end_requirement.required_on_site_at,
                    "end_at": end_requirement.releasable_at,
                    "allocation_strength": AllocationStrength.HARD,
                    "assignment_source": RecordSource.MANUAL,
                    "locked": True,
                    "notes": "DEMONSTRATION DATA",
                },
            )
            created += was_created

        demo_movement, was_created = get_or_create(
            session,
            EquipmentMovement,
            {"movement_code": "DEMO-MV-01"},
            {
                "origin_location_id": oxford.id,
                "destination_location_id": roskilde.location_id,
                "depart_after": datetime(2026, 6, 16, 8, tzinfo=london),
                "arrive_by": datetime(2026, 6, 18, 6, tzinfo=london),
                "status": MovementStatus.CONFIRMED,
                "source": RecordSource.MANUAL,
                "locked": True,
                "notes": "DEMONSTRATION DATA",
            },
        )
        created += was_created
        demo_load, was_created = get_or_create(
            session,
            Load,
            {"equipment_movement_id": demo_movement.id, "load_number": 1},
            {
                "lorry_id": lorry.id,
                "lorry_type_id": lorry_type.id,
                "status": LoadStatus.CONFIRMED,
                "planned_departure_at": demo_movement.depart_after,
                "planned_arrival_at": demo_movement.arrive_by,
                "estimated_distance_km": Decimal("1000"),
                "estimated_cost": Decimal("2400"),
                "locked": True,
                "notes": "DEMONSTRATION DATA",
            },
        )
        created += was_created
        for asset in demo_assets:
            _, was_created = get_or_create(
                session,
                LoadItem,
                {"load_id": demo_load.id, "equipment_asset_id": asset.id},
                {"quantity": 1, "notes": "DEMONSTRATION DATA"},
            )
            created += was_created

        crew_move, was_created = get_or_create(
            session,
            CrewMovement,
            {"movement_code": "CM16-DEMO"},
            {
                "origin_location_id": oxford.id,
                "destination_location_id": roskilde.location_id,
                "tentmaster_id": tentmasters[0].id,
                "van_id": van.id,
                "depart_after": datetime(2026, 6, 17, 8, tzinfo=london),
                "arrive_by": datetime(2026, 6, 18, 7, tzinfo=london),
                "status": MovementStatus.CONFIRMED,
                "locked": True,
                "notes": "DEMONSTRATION DATA",
            },
        )
        created += was_created
        for crew_member in crew_members:
            _, was_created = get_or_create(
                session,
                CrewMovementPassenger,
                {"crew_movement_id": crew_move.id, "crew_member_id": crew_member.id},
                {"quantity": 1, "notes": "DEMONSTRATION DATA"},
            )
            created += was_created
        for leg_sequence, mode, origin_label, destination_label, depart, arrive in (
            (
                1,
                JourneyMode.VAN,
                "Oxford Yard",
                "UK ferry terminal",
                datetime(2026, 6, 17, 8, tzinfo=london),
                datetime(2026, 6, 17, 13, tzinfo=london),
            ),
            (
                2,
                JourneyMode.FERRY,
                "UK ferry terminal",
                "Continental transfer",
                datetime(2026, 6, 17, 15, tzinfo=london),
                datetime(2026, 6, 18, 7, tzinfo=london),
            ),
        ):
            _, was_created = get_or_create(
                session,
                CrewJourneyLeg,
                {"crew_movement_id": crew_move.id, "sequence": leg_sequence},
                {
                    "mode": mode,
                    "origin_label": origin_label,
                    "destination_label": destination_label,
                    "depart_at": depart,
                    "arrive_at": arrive,
                    "notes": "DEMONSTRATION DATA",
                },
            )
            created += was_created

        invoice, was_created = get_or_create(
            session,
            SupplierInvoice,
            {"supplier_reference": "DEMO-INV-01"},
            {
                "haulier_id": haulier.id,
                "supplier_name": haulier.name,
                "invoice_date": date(2026, 6, 20),
                "total_amount": Decimal("2500"),
                "notes": "DEMONSTRATION DATA — not a real invoice.",
            },
        )
        created += was_created
        _, was_created = get_or_create(
            session,
            LoadCostAllocation,
            {
                "supplier_invoice_id": invoice.id,
                "load_id": demo_load.id,
                "job_id": roskilde.id,
                "category": CostCategory.HAULAGE,
            },
            {"allocated_amount": Decimal("2500"), "notes": "DEMONSTRATION DATA"},
        )
        created += was_created

    session.commit()
    return created


def main() -> None:
    """Apply migrations and load idempotent demonstration reference data."""

    settings = get_settings()
    alembic_config = Config(PROJECT_ROOT / "alembic.ini")
    alembic_config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_config, "head")
    with SessionLocal() as session:
        created = seed_development_data(session, include_operational_demo=True)
    print(f"Development database is ready; created {created} demonstration records.")


if __name__ == "__main__":
    main()
