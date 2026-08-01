from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import CrewMember, Location, Van
from app.services.crew_movements import CrewMovementService, LateArrivalError, VanCapacityError


def movement_setup(session: Session):  # type: ignore[no-untyped-def]
    seed_development_data(session)
    locations = session.scalars(select(Location).order_by(Location.id)).all()
    van = session.scalar(select(Van))
    crew = session.scalars(select(CrewMember).limit(2)).all()
    assert van is not None and len(locations) >= 2 and len(crew) >= 2
    start = datetime(2026, 7, 1, 8, tzinfo=UTC)
    service = CrewMovementService(session)
    movement = service.create(
        {
            "movement_code": "CM16",
            "origin_location_id": locations[0].id,
            "destination_location_id": locations[1].id,
            "van_id": van.id,
            "depart_after": start,
            "arrive_by": start + timedelta(hours=6),
        }
    )
    return service, movement, crew, van, start


def test_passengers_and_van_capacity(session: Session) -> None:
    service, movement, crew, van, _ = movement_setup(session)
    van.passenger_capacity = 1
    session.commit()
    service.add_passenger(movement.id, crew_member_id=crew[0].id)
    with pytest.raises(VanCapacityError):
        service.add_passenger(movement.id, crew_member_id=crew[1].id)


def test_multileg_journey_and_late_arrival(session: Session) -> None:
    service, movement, _, _, start = movement_setup(session)
    service.add_leg(
        movement.id,
        {
            "sequence": 1,
            "mode": "van",
            "origin_label": "Oxford",
            "destination_label": "Port",
            "depart_at": start,
            "arrive_at": start + timedelta(hours=2),
        },
    )
    service.add_leg(
        movement.id,
        {
            "sequence": 2,
            "mode": "ferry",
            "origin_label": "Port",
            "destination_label": "Site",
            "depart_at": start + timedelta(hours=3),
            "arrive_at": start + timedelta(hours=7),
        },
    )
    assert len(movement.legs) == 2
    with pytest.raises(LateArrivalError):
        service.validate_arrival(movement, start + timedelta(hours=6))


def test_placeholder_passenger(session: Session) -> None:
    service, movement, _, _, _ = movement_setup(session)
    passenger = service.add_passenger(movement.id, placeholder_label="Local crew", quantity=2)
    assert service.passenger_names(movement) == ["2 × Local crew"]
    assert passenger.crew_member_id is None
