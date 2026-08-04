from __future__ import annotations

from datetime import UTC, datetime, timedelta
from datetime import date as date_

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import (
    EquipmentType,
    Location,
    LocationType,
    LorryType,
)
from app.models.jobs import CommercialStatus, Job
from app.models.logistics import EquipmentMovement, Load, LoadItem, MovementStatus
from app.services.flow import FlowService, _pack_job_columns
from app.services.jobs import JobService


def test_flow_diagram_and_route(session: Session, client) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session, include_operational_demo=True)
    flow = FlowService(session).build(date_(2026, 5, 1), date_(2026, 6, 30))
    assert flow.columns
    assert flow.columns[0].kind == "yard"
    response = client.get("/planning/flow?start=2026-05-01&end=2026-06-30")
    assert response.status_code == 200
    assert b"Loads diagram" in response.content or b"loads diagram" in response.content.lower()
    # Continuous overlay markup
    assert b"flow-job-overlay" in response.content or not flow.job_blocks


def test_flow_diagram_empty_range_has_days(session: Session) -> None:
    seed_development_data(session, include_operational_demo=True)
    flow = FlowService(session).build(date_(2027, 1, 1), date_(2027, 1, 31))
    assert flow.days
    assert len(flow.days) == 31
    # No jobs in that winter range for demo data
    assert flow.job_blocks == [] or all(
        b.top >= flow.header_height for b in flow.job_blocks
    )


def test_pack_job_columns_reuses_lanes() -> None:
    early = (
        datetime(2026, 6, 1, tzinfo=UTC),
        datetime(2026, 6, 10, tzinfo=UTC),
    )
    late = (
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 7, 10, tzinfo=UTC),
    )
    overlap = (
        datetime(2026, 6, 5, tzinfo=UTC),
        datetime(2026, 6, 15, tzinfo=UTC),
    )
    packed = _pack_job_columns({1: early, 2: late, 3: overlap})
    assert packed[1] == packed[2]  # sequential reuse
    assert packed[3] != packed[1]  # concurrent needs another lane


def test_flow_shows_continuous_blocks_and_yard_markers(session: Session) -> None:
    seed_development_data(session)
    yard = session.scalar(select(Location).where(Location.location_type == LocationType.YARD))
    site = Location(name="Flow Loads Site", location_type=LocationType.SITE)
    session.add(site)
    session.flush()
    lorry = session.scalar(select(LorryType).where(LorryType.active.is_(True)))
    equipment_type = session.scalar(select(EquipmentType).where(EquipmentType.code == "K"))
    assert yard is not None and lorry is not None and equipment_type is not None

    up = datetime(2026, 6, 20, 18, tzinfo=UTC)
    job = Job(
        job_code="FLOW-LOADS-1",
        name="Flow loads job",
        customer_name="Fixture",
        location_id=site.id,
        commercial_status=CommercialStatus.QUOTED,
    )
    session.add(job)
    session.commit()
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-K",
            "quantity": 1,
            "contracted_up_at": up,
            "contracted_down_at": up + timedelta(days=5),
        },
    )

    depart = up - timedelta(days=3)
    arrive = up - timedelta(days=2)
    movement = EquipmentMovement(
        movement_code="FLOW-LD-MV",
        origin_location_id=yard.id,
        destination_location_id=site.id,
        depart_after=depart,
        arrive_by=arrive,
        status=MovementStatus.PLANNED,
    )
    movement.loads.append(
        Load(
            load_number=7,
            lorry_type_id=lorry.id,
            items=[LoadItem(equipment_type_id=equipment_type.id, quantity=2)],
        )
    )
    session.add(movement)
    session.commit()

    flow = FlowService(session).build(date_(2026, 6, 10), date_(2026, 6, 25))
    assert flow.columns[0].kind == "yard"

    # Yard shows out marker on depart day (may be grouped)
    assert any(
        mark.kind == "yard_out" and 7 in mark.load_numbers and mark.day == depart.date()
        for mark in flow.yard_marks
    )

    # Continuous job block with arrival event + visible job code
    blocks = [b for b in flow.job_blocks if b.job_code == "FLOW-LOADS-1"]
    assert len(blocks) == 1
    block = blocks[0]
    assert block.job_code == "FLOW-LOADS-1"
    assert block.span_days >= 5
    assert block.height == block.span_days * flow.row_height
    assert any(ev.kind == "arrival" and "L7" in ev.text for ev in block.events)
    # Contract Up band present
    assert block.up_height > 0

    # Edge from yard to job on correct day rows
    edge = next(e for e in flow.edges if 7 in e.load_numbers)
    assert edge.origin_name == yard.name
    assert "L7" in edge.label
    # y coords include header offset and fall within the diagram height
    assert flow.header_height <= edge.y1 < flow.height
    assert flow.header_height <= edge.y2 < flow.height


def test_flow_clamps_late_departure_onto_job_block(session: Session) -> None:
    """Stale just-in-time job→job leave still shows ↑ on the donor job's last day."""
    seed_development_data(session)
    site_a = Location(name="Donor Site", location_type=LocationType.SITE)
    site_b = Location(name="Receiver Site", location_type=LocationType.SITE)
    session.add_all([site_a, site_b])
    session.flush()
    lorry = session.scalar(select(LorryType).where(LorryType.active.is_(True)))
    equipment_type = session.scalar(select(EquipmentType).where(EquipmentType.code == "K"))
    assert lorry is not None and equipment_type is not None

    donor = Job(
        job_code="DONOR-1",
        name="Donor",
        customer_name="Fixture",
        location_id=site_a.id,
        commercial_status=CommercialStatus.CONFIRMED,
    )
    receiver = Job(
        job_code="RECV-1",
        name="Receiver",
        customer_name="Fixture",
        location_id=site_b.id,
        commercial_status=CommercialStatus.CONFIRMED,
    )
    session.add_all([donor, receiver])
    session.commit()
    up_a = datetime(2026, 7, 10, 12, tzinfo=UTC)
    JobService(session).add_tent_requirement(
        donor.id,
        {
            "sequence": "K",
            "quantity": 1,
            "contracted_up_at": up_a,
            "contracted_down_at": up_a + timedelta(days=4),
        },
    )
    up_b = datetime(2026, 8, 5, 12, tzinfo=UTC)
    JobService(session).add_tent_requirement(
        receiver.id,
        {
            "sequence": "K",
            "quantity": 1,
            "contracted_up_at": up_b,
            "contracted_down_at": up_b + timedelta(days=4),
        },
    )
    # Depart long after donor break trail ends (old just-in-time behaviour)
    late_depart = up_b - timedelta(days=2)
    movement = EquipmentMovement(
        movement_code="LATE-MV",
        origin_location_id=site_a.id,
        destination_location_id=site_b.id,
        depart_after=late_depart,
        arrive_by=up_b - timedelta(days=1),
        status=MovementStatus.PLANNED,
    )
    movement.loads.append(
        Load(
            load_number=99,
            lorry_type_id=lorry.id,
            items=[LoadItem(equipment_type_id=equipment_type.id, quantity=1)],
        )
    )
    session.add(movement)
    session.commit()

    flow = FlowService(session).build(date_(2026, 7, 1), date_(2026, 8, 15))
    donor_block = next(b for b in flow.job_blocks if b.job_code == "DONOR-1")
    deps = [ev for ev in donor_block.events if ev.kind == "departure" and ev.load_number == 99]
    assert deps, "late departure should still appear on donor block"
    assert deps[0].day_offset == donor_block.span_days - 1


def test_flow_groups_convoy_loads_on_one_arrow(session: Session) -> None:
    """Three loads same yard→site corridor share one arrow labelled L7–L9 (or L7, L8, L9)."""
    seed_development_data(session)
    yard = session.scalar(select(Location).where(Location.location_type == LocationType.YARD))
    site = Location(name="Convoy Site", location_type=LocationType.SITE)
    session.add(site)
    session.flush()
    lorry = session.scalar(select(LorryType).where(LorryType.active.is_(True)))
    equipment_type = session.scalar(select(EquipmentType).where(EquipmentType.code == "K"))
    assert yard is not None and lorry is not None and equipment_type is not None

    up = datetime(2026, 6, 20, 18, tzinfo=UTC)
    job = Job(
        job_code="CONVOY-1",
        name="Convoy job",
        customer_name="Fixture",
        location_id=site.id,
        commercial_status=CommercialStatus.QUOTED,
    )
    session.add(job)
    session.commit()
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-K",
            "quantity": 1,
            "contracted_up_at": up,
            "contracted_down_at": up + timedelta(days=5),
        },
    )
    depart = up - timedelta(days=3)
    arrive = up - timedelta(days=2)
    for n in (7, 8, 9):
        movement = EquipmentMovement(
            movement_code=f"CNV-MV-{n}",
            origin_location_id=yard.id,
            destination_location_id=site.id,
            depart_after=depart,
            arrive_by=arrive,
            status=MovementStatus.PLANNED,
        )
        movement.loads.append(
            Load(
                load_number=n,
                lorry_type_id=lorry.id,
                items=[LoadItem(equipment_type_id=equipment_type.id, quantity=1)],
            )
        )
        session.add(movement)
    session.commit()

    flow = FlowService(session).build(date_(2026, 6, 10), date_(2026, 6, 25))
    convoy = [e for e in flow.edges if set(e.load_numbers) >= {7, 8, 9}]
    assert len(convoy) == 1
    assert convoy[0].label in {"L7–L9", "L7, L8, L9"}
    yard_out = next(
        m for m in flow.yard_marks if m.kind == "yard_out" and m.day == depart.date()
    )
    assert set(yard_out.load_numbers) >= {7, 8, 9}
    assert yard_out.text in {"out L7–L9", "out L7, L8, L9"}


def test_flow_clamps_early_arrival_onto_job_block(session: Session) -> None:
    """Leave-at-break arrivals weeks before build still show ↓ on first Build day."""
    seed_development_data(session)
    site_a = Location(name="Early Donor Site", location_type=LocationType.SITE)
    site_b = Location(name="Early Recv Site", location_type=LocationType.SITE)
    session.add_all([site_a, site_b])
    session.flush()
    lorry = session.scalar(select(LorryType).where(LorryType.active.is_(True)))
    equipment_type = session.scalar(select(EquipmentType).where(EquipmentType.code == "K"))
    assert lorry is not None and equipment_type is not None

    receiver = Job(
        job_code="EARLY-RECV",
        name="Early receiver",
        customer_name="Fixture",
        location_id=site_b.id,
        commercial_status=CommercialStatus.CONFIRMED,
    )
    session.add(receiver)
    session.commit()
    up_b = datetime(2026, 8, 20, 12, tzinfo=UTC)
    JobService(session).add_tent_requirement(
        receiver.id,
        {
            "sequence": "K",
            "quantity": 1,
            "contracted_up_at": up_b,
            "contracted_down_at": up_b + timedelta(days=4),
        },
    )
    early_arrive = up_b - timedelta(days=20)
    movement = EquipmentMovement(
        movement_code="EARLY-MV",
        origin_location_id=site_a.id,
        destination_location_id=site_b.id,
        depart_after=early_arrive - timedelta(days=1),
        arrive_by=early_arrive,
        status=MovementStatus.PLANNED,
    )
    movement.loads.append(
        Load(
            load_number=88,
            lorry_type_id=lorry.id,
            items=[LoadItem(equipment_type_id=equipment_type.id, quantity=1)],
        )
    )
    session.add(movement)
    session.commit()

    flow = FlowService(session).build(date_(2026, 7, 1), date_(2026, 9, 1))
    block = next(b for b in flow.job_blocks if b.job_code == "EARLY-RECV")
    arrs = [ev for ev in block.events if ev.kind == "arrival" and ev.load_number == 88]
    assert arrs, "early arrival should pin to first day of receiver block"
    assert arrs[0].day_offset == 0


def test_flow_diagram_uses_bounded_queries(session: Session, test_engine) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session, include_operational_demo=True)
    statements = 0

    def count_queries(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal statements
        statements += 1

    event.listen(test_engine, "before_cursor_execute", count_queries)
    try:
        FlowService(session).build(date_(2026, 4, 1), date_(2026, 9, 30))
    finally:
        event.remove(test_engine, "before_cursor_execute", count_queries)
    assert statements <= 20
