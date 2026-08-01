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
    CrewMember,
    EquipmentAsset,
    EquipmentType,
    Haulier,
    Location,
    LocationType,
    Lorry,
    LorryType,
    OwnershipType,
    TentConfiguration,
    TentConfigurationRequirement,
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
from app.models.crew_planning import CrewAssignment
from app.models.equipment_planning import AllocationStrength, EquipmentAssignment
from app.models.jobs import (
    CommercialStatus,
    Job,
    JobTentRequirement,
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

    equipment_definitions = (
        ("END", "End", "section", TrackingMode.INDIVIDUAL, BuildStage.MAIN_SECTIONS),
        ("MIDDLE", "Middle", "section", TrackingMode.INDIVIDUAL, BuildStage.MAIN_SECTIONS),
        ("POLE", "Pole", "pole", TrackingMode.INDIVIDUAL, BuildStage.POLES_AND_ANCHORS),
        (
            "ANCHOR_SET",
            "Anchor set",
            "anchor",
            TrackingMode.INDIVIDUAL,
            BuildStage.POLES_AND_ANCHORS,
        ),
        (
            "ANCILLARY_KIT",
            "Ancillary kit",
            "ancillary",
            TrackingMode.QUANTITY,
            BuildStage.COMPLETION_AND_ANCILLARY,
        ),
    )
    equipment_types: dict[str, EquipmentType] = {}
    for code, name, category, tracking_mode, stage in equipment_definitions:
        equipment_type, was_created = get_or_create(
            session,
            EquipmentType,
            {"code": code},
            {
                "name": name,
                "category": category,
                "tent_family_id": kayam.id,
                "tracking_mode": tracking_mode,
                "default_build_stage": stage,
                "notes": "DEMONSTRATION DATA — verify capacity and compatibility before use.",
            },
        )
        equipment_types[code] = equipment_type
        created += was_created

    configuration_components = {
        4: {"END": 2, "MIDDLE": 1, "POLE": 4, "ANCHOR_SET": 1, "ANCILLARY_KIT": 1},
        6: {"END": 2, "MIDDLE": 2, "POLE": 6, "ANCHOR_SET": 1, "ANCILLARY_KIT": 1},
        10: {"END": 2, "MIDDLE": 4, "POLE": 10, "ANCHOR_SET": 1, "ANCILLARY_KIT": 1},
        12: {"END": 2, "MIDDLE": 5, "POLE": 12, "ANCHOR_SET": 1, "ANCILLARY_KIT": 1},
    }
    for pole_count, component_quantities in configuration_components.items():
        configuration, was_created = get_or_create(
            session,
            TentConfiguration,
            {"tent_family_id": kayam.id, "name": f"Kayam {pole_count}-pole"},
            {
                "pole_count": pole_count,
                "default_build_hours": Decimal("0"),
                "default_strike_hours": Decimal("0"),
                "minimum_crew": 0,
                "preferred_crew": 0,
                "notes": "DEMONSTRATION DATA — set verified durations and crew levels.",
            },
        )
        if "DEMONSTRATION DATA" in (configuration.notes or ""):
            configuration.default_build_hours = Decimal("24")
            configuration.default_strike_hours = Decimal("16")
            configuration.minimum_crew = 4
            configuration.preferred_crew = 6
        created += was_created
        for equipment_code, quantity in component_quantities.items():
            equipment_type = equipment_types[equipment_code]
            _, was_created = get_or_create(
                session,
                TentConfigurationRequirement,
                {
                    "tent_configuration_id": configuration.id,
                    "equipment_type_id": equipment_type.id,
                    "required_stage": equipment_type.default_build_stage,
                },
                {
                    "quantity": quantity,
                    "individually_assignable": equipment_type.tracking_mode
                    == TrackingMode.INDIVIDUAL,
                },
            )
            created += was_created

    asset_codes = ["K1", "K2", "K3"] + [f"M{number}" for number in range(1, 6)]
    asset_codes += [f"P{number}" for number in range(1, 21)] + ["A1", "A2"]
    asset_types = {
        "K": equipment_types["END"],
        "M": equipment_types["MIDDLE"],
        "P": equipment_types["POLE"],
        "A": equipment_types["ANCHOR_SET"],
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

    crew_members: list[CrewMember] = []
    for number in range(1, 5):
        crew_member, was_created = get_or_create(
            session,
            CrewMember,
            {"name": f"Demo Crew {number}"},
            {
                "role": "Tent crew",
                "employment_type": "Demonstration",
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

    lorry_type, was_created = get_or_create(
        session,
        LorryType,
        {"name": "Standard artic"},
        {
            "section_capacity_units": Decimal("12"),
            "pole_capacity_units": Decimal("0"),
            "ancillary_capacity_units": Decimal("0"),
            "payload_kg": Decimal("0"),
            "passenger_capacity": 0,
            "default_cost_per_km": Decimal("0"),
            "minimum_load_cost": Decimal("0"),
            "notes": "DEMONSTRATION DATA — zero means an unverified capacity or rate.",
        },
    )
    created += was_created
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

    configurations_by_poles = {
        configuration.pole_count: configuration
        for configuration in session.scalars(
            select(TentConfiguration).where(TentConfiguration.tent_family_id == kayam.id)
        )
    }
    london = ZoneInfo("Europe/London")
    demo_jobs = (
        (
            "DEMO-ROS-26",
            "Roskilde Demonstration",
            demo_sites["Roskilde Demo Site"],
            datetime(2026, 6, 18, 8, tzinfo=london),
            datetime(2026, 6, 22, 20, tzinfo=london),
            datetime(2026, 6, 30, 8, tzinfo=london),
            10,
            CommercialStatus.CONFIRMED,
            PlanningStatus.PLANNER_APPROVED,
        ),
        (
            "DEMO-SCO-26",
            "Scotland Demonstration",
            demo_sites["Scotland Demo Site"],
            datetime(2026, 7, 4, 8, tzinfo=london),
            datetime(2026, 7, 6, 20, tzinfo=london),
            datetime(2026, 7, 12, 8, tzinfo=london),
            6,
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
            4,
            CommercialStatus.ENQUIRY,
            PlanningStatus.NOT_PLANNED,
        ),
    )
    job_service = JobService(session)
    jobs_by_code: dict[str, Job] = {}
    for code, name, site, access_at, up_at, strike_at, poles, commercial, planning in demo_jobs:
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
                "must_be_up_at": up_at,
                "show_start_at": up_at,
                "show_end_at": strike_at,
                "strike_available_at": strike_at,
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
        _, requirement_created = get_or_create(
            session,
            JobTentRequirement,
            {"job_id": job.id, "tent_configuration_id": configurations_by_poles[poles].id},
            {"quantity": 1, "notes": "DEMONSTRATION DATA"},
        )
        created += requirement_created
        session.expire(job, ["tent_requirements", "equipment_requirements", "phases"])
        job_service.regenerate_requirements(job)
        job_service.generate_phases(job)

    if include_operational_demo:
        roskilde = jobs_by_code["DEMO-ROS-26"]
        roskilde_build = next(
            phase for phase in roskilde.phases if phase.phase_type == PhaseType.BUILD
        )
        for index, crew_member in enumerate(crew_members):
            _, was_created = get_or_create(
                session,
                CrewAssignment,
                {"job_phase_id": roskilde_build.id, "crew_member_id": crew_member.id},
                {
                    "tentmaster_id": tentmasters[index].id,
                    "start_at": roskilde_build.start_at,
                    "end_at": roskilde_build.end_at,
                    "role": "Tent crew",
                    "assignment_source": RecordSource.MANUAL,
                    "locked": True,
                    "notes": "DEMONSTRATION DATA",
                },
            )
            created += was_created

        end_requirement = next(
            requirement
            for requirement in roskilde.equipment_requirements
            if requirement.equipment_type.code == "END"
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
        for sequence, mode, origin_label, destination_label, depart, arrive in (
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
                {"crew_movement_id": crew_move.id, "sequence": sequence},
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
