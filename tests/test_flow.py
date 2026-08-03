from __future__ import annotations

from datetime import UTC, datetime, timedelta
from datetime import date as date_

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import (
    EquipmentAsset,
    EquipmentType,
    Location,
    LocationType,
    LorryType,
)
from app.models.jobs import CommercialStatus, Job
from app.models.logistics import EquipmentMovement, Load, LoadItem, MovementStatus
from app.services.flow import FlowService
from app.services.jobs import JobService


def test_flow_diagram_and_route(session: Session, client) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session, include_operational_demo=True)
    flow = FlowService(session).build(date_(2026, 5, 1), date_(2026, 6, 30))
    assert flow.nodes
    assert flow.edges
    yard_index = next(i for i, node in enumerate(flow.nodes) if node.name == "Oxford Yard")
    assert yard_index == 0  # yard/depot locations sort before ordinary sites

    response = client.get("/planning/flow?start=2026-05-01&end=2026-06-30")
    assert response.status_code == 200
    assert b"flow-edge" in response.content


def test_flow_diagram_empty_range_has_no_nodes(session: Session) -> None:
    seed_development_data(session, include_operational_demo=True)
    flow = FlowService(session).build(date_(2027, 1, 1), date_(2027, 1, 31))
    assert flow.nodes == []
    assert flow.edges == []


def test_flow_edge_summarises_multiple_loads(session: Session) -> None:
    seed_development_data(session, include_operational_demo=True)
    origin = Location(name="Flow Test Yard", location_type=LocationType.YARD)
    destination = Location(name="Flow Test Site", location_type=LocationType.SITE)
    session.add_all([origin, destination])
    session.flush()
    lorry_type = session.scalar(select(LorryType))
    equipment_type = session.scalar(select(EquipmentType))
    asset = session.scalar(select(EquipmentAsset))
    assert lorry_type is not None and equipment_type is not None and asset is not None
    start = datetime(2026, 5, 10, 8, tzinfo=UTC)
    movement = EquipmentMovement(
        movement_code="FLOW-TEST-1",
        origin_location_id=origin.id,
        destination_location_id=destination.id,
        depart_after=start,
        arrive_by=start + timedelta(hours=6),
        status=MovementStatus.PLANNED,
    )
    movement.loads.append(
        Load(
            load_number=1,
            lorry_type_id=lorry_type.id,
            items=[LoadItem(equipment_type_id=equipment_type.id, quantity=3)],
        )
    )
    movement.loads.append(
        Load(
            load_number=2,
            lorry_type_id=lorry_type.id,
            items=[LoadItem(equipment_asset_id=asset.id)],
        )
    )
    session.add(movement)
    session.commit()

    flow = FlowService(session).build(date_(2026, 5, 10), date_(2026, 5, 10))
    edge = next(edge for edge in flow.edges if edge.movement_id == movement.id)
    assert edge.status == "planned"
    assert "2 load(s)" in edge.subtitle
    assert asset.asset_code in edge.subtitle


def test_flow_diagram_shows_job_cell_with_tent_sequence(session: Session) -> None:
    seed_development_data(session, include_operational_demo=True)
    location = Location(name="Flow Cell Site", location_type=LocationType.SITE)
    session.add(location)
    session.flush()
    start = datetime(2026, 5, 10, tzinfo=UTC)
    job = Job(
        job_code="FLOW-CELL-1",
        name="Flow cell job",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.CONFIRMED,
        site_access_at=start,
    )
    session.add(job)
    session.commit()
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": start,
            "contracted_down_at": start + timedelta(days=2),
        },
    )
    # The cell block spans the job's whole window: Build lead (5d before Up) through Break
    # trail (3d after Down) — 2026-05-05 through 2026-05-14 here.
    flow = FlowService(session).build(date_(2026, 5, 5), date_(2026, 5, 14))
    node = next(node for node in flow.nodes if node.location_id == location.id)
    first_block = flow.days[0].cells[node.location_id][0]
    last_block = flow.days[-1].cells[node.location_id][0]
    assert first_block.label == "FLOW-CELL-1"
    assert "KMMMK" in first_block.subtitle
    assert first_block.segment == "start"
    assert last_block.segment == "end"


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
    assert statements <= 15
