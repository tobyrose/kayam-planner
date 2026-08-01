from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
    equipment_type = session.scalar(select(EquipmentType).where(EquipmentType.code == "POLE"))
    assert equipment_type is not None
    equipment_type.pole_capacity_units = 1
    lorry_type.pole_capacity_units = 100
    service.add_item({"load_id": load.id, "equipment_type_id": equipment_type.id, "quantity": 1})
    assert service.capacity(load).status == "within"
    load.items[0].quantity = 10000
    session.commit()
    assert service.capacity(load).status == "over"


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
    assert second.display_code.endswith("LD2")


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
        next(item for item in job.equipment_requirements if item.equipment_type.code == "END")
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
