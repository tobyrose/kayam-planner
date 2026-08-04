from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import EquipmentAsset, EquipmentType, Location, LorryType
from app.models.jobs import Job
from app.models.logistics import Load
from app.services.equipment_planning import EquipmentPlanningService
from app.services.logistics import (
    LocationContinuityError,
    LockedLoadError,
    LogisticsService,
)


def seeded_logistics(session: Session) -> tuple[LogisticsService, Location, Location, LorryType]:
    seed_development_data(session)
    locations = session.scalars(select(Location).order_by(Location.id)).all()
    lorry_type = session.scalar(select(LorryType))
    assert len(locations) >= 2 and lorry_type is not None
    return LogisticsService(session), locations[0], locations[1], lorry_type


def create_load(
    service: LogisticsService,
    origin: Location,
    destination: Location,
    lorry_type: LorryType,
    *,
    code: str = "TEST-MV",
    number: int = 1,
) -> Load:
    start = datetime(2026, 6, 1, 8, tzinfo=UTC)
    movement = service.create_movement(
        {
            "movement_code": code,
            "origin_location_id": origin.id,
            "destination_location_id": destination.id,
            "depart_after": start,
            "arrive_by": start + timedelta(hours=8),
        }
    )
    return service.create_load(
        {
            "equipment_movement_id": movement.id,
            "load_number": number,
            "lorry_type_id": lorry_type.id,
        }
    )


def test_load_capacity_within_and_over_limit(session: Session) -> None:
    service, origin, destination, lorry_type = seeded_logistics(session)
    load = create_load(service, origin, destination, lorry_type)
    equipment_type = session.scalar(select(EquipmentType).where(EquipmentType.code == "K"))
    assert equipment_type is not None
    # Q042: K = 1.2 points; Flat = 7.2 → six Ks = 7.2 exactly (within/near boundary is 85%)
    lorry_type.section_capacity_units = Decimal("7.2")
    equipment_type.section_capacity_units = Decimal("1.2")
    service.add_item({"load_id": load.id, "equipment_type_id": equipment_type.id, "quantity": 1})
    cap = service.capacity(load)
    assert cap.status == "within"
    assert cap.section_units == Decimal("1.2")
    load.items[0].quantity = 10  # 12 points on 7.2 capacity
    session.commit()
    assert service.capacity(load).status == "over"
    assert service.capacity(load).section_units == Decimal("12.0")


def test_one_movement_supports_multiple_numbered_loads(session: Session) -> None:
    service, origin, destination, lorry_type = seeded_logistics(session)
    first = create_load(service, origin, destination, lorry_type)
    second = service.create_load(
        {
            "equipment_movement_id": first.equipment_movement_id,
            "load_number": 2,
            "lorry_type_id": lorry_type.id,
        }
    )
    assert second.display_code == "L2"


def test_create_movement_and_load_auto_allocate_codes_and_numbers(session: Session) -> None:
    service, origin, destination, lorry_type = seeded_logistics(session)
    movement = service.create_movement(
        {
            "origin_location_id": origin.id,
            "destination_location_id": destination.id,
            "depart_after": datetime(2026, 6, 1, 8, tzinfo=UTC),
            "arrive_by": datetime(2026, 6, 1, 16, tzinfo=UTC),
        }
    )
    assert movement.movement_code.startswith("MV-")
    load = service.create_load(
        {
            "equipment_movement_id": movement.id,
            "lorry_type_id": lorry_type.id,
        }
    )
    assert load.load_number == service.next_load_number() - 1
    assert load.load_number >= 1


def test_new_load_form_omits_movement_code_and_standard_artic(
    session: Session, client
) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session)
    response = client.get("/loads/new")
    assert response.status_code == 200
    assert 'name="movement_code"' not in response.text
    assert "Standard artic" not in response.text
    assert "depart_after_date" in response.text
    assert 'type="time"' in response.text
    assert "Curtain" in response.text or "Flat" in response.text


def test_new_load_form_posts_with_date_and_time(
    session: Session, client
) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session)
    locations = session.scalars(select(Location).order_by(Location.id)).all()
    lorry = session.scalar(select(LorryType).where(LorryType.name == "Flat"))
    assert len(locations) >= 2 and lorry is not None
    response = client.post(
        "/loads/new",
        data={
            "origin_location_id": str(locations[0].id),
            "destination_location_id": str(locations[1].id),
            "depart_after_date": "2026-06-10",
            "depart_after_time": "09:30",
            "arrive_by_date": "2026-06-11",
            "arrive_by_time": "18:00",
            "lorry_type_id": str(lorry.id),
            "status": "required",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/loads/")
    load = session.scalar(select(Load).order_by(Load.id.desc()))
    assert load is not None
    assert load.load_number >= 1


def test_asset_location_continuity_and_locked_load(session: Session) -> None:
    service, origin, destination, lorry_type = seeded_logistics(session)
    asset = session.scalar(select(EquipmentAsset).where(EquipmentAsset.asset_code == "K1"))
    assert asset is not None
    asset.initial_location_id = origin.id
    session.commit()
    load = create_load(service, destination, origin, lorry_type)
    with pytest.raises(LocationContinuityError):
        service.add_item({"load_id": load.id, "equipment_asset_id": asset.id})

    valid = create_load(service, origin, destination, lorry_type, code="VALID-MV")
    valid.locked = True
    session.commit()
    with pytest.raises(LockedLoadError):
        service.add_item({"load_id": valid.id, "equipment_asset_id": asset.id})


def test_transition_requirements_are_generated_without_committing_loads(session: Session) -> None:
    seed_development_data(session)
    asset = session.scalar(select(EquipmentAsset).where(EquipmentAsset.asset_code == "K1"))
    jobs = session.scalars(
        select(Job)
        .where(Job.job_code.in_(["DEMO-ROS-26", "DEMO-SCO-26"]))
        .order_by(Job.site_access_at)
    ).all()
    assert asset is not None and len(jobs) == 2
    requirements = [
        next(item for item in job.equipment_requirements if item.equipment_type.code == "K")
        for job in jobs
    ]
    planning = EquipmentPlanningService(session)
    for requirement in requirements:
        planning.assign(
            {
                "job_equipment_requirement_id": requirement.id,
                "equipment_asset_id": asset.id,
                "start_at": requirement.required_on_site_at,
                "end_at": requirement.releasable_at,
                "allocation_strength": "hard",
                "assignment_source": "manual",
                "locked": True,
                "status": "active",
            }
        )
    generated = LogisticsService(session).generate_movement_requirements()
    assert len(generated) == 1
    assert generated[0].source.value == "generated"
    assert generated[0].loads == []
