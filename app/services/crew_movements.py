from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.models.administration import CrewMember
from app.models.crew_movements import (
    CrewJourneyLeg,
    CrewMovement,
    CrewMovementPassenger,
    JourneyMode,
)


class CrewMovementError(Exception):
    pass


class VanCapacityError(CrewMovementError):
    pass


class LateArrivalError(CrewMovementError):
    pass


class CrewMovementData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movement_code: str = Field(min_length=1)
    origin_location_id: int
    destination_location_id: int
    tentmaster_id: int | None = None
    van_id: int | None = None
    depart_after: datetime
    arrive_by: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def valid_dates(self) -> CrewMovementData:
        if self.origin_location_id == self.destination_location_id:
            raise ValueError("Origin and destination must differ")
        if self.arrive_by <= self.depart_after:
            raise ValueError("Arrival must be after departure")
        return self


class CrewMovementService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: dict[str, Any]) -> CrewMovement:
        movement = CrewMovement(**CrewMovementData.model_validate(payload).model_dump())
        self.session.add(movement)
        self.session.commit()
        return movement

    def add_leg(self, movement_id: int, payload: dict[str, Any]) -> CrewJourneyLeg:
        movement = self._movement(movement_id)
        if movement.locked:
            raise CrewMovementError("Locked crew movements cannot be changed")
        leg = CrewJourneyLeg(**payload)
        movement.legs.append(leg)
        self.session.commit()
        return leg

    def add_passenger(
        self,
        movement_id: int,
        *,
        crew_member_id: int | None = None,
        placeholder_label: str | None = None,
        quantity: int = 1,
        joining_tentmaster_id: int | None = None,
        leaving_tentmaster_id: int | None = None,
    ) -> CrewMovementPassenger:
        movement = self._movement(movement_id)
        if movement.locked:
            raise CrewMovementError("Locked crew movements cannot be changed")
        if (crew_member_id is None) == (not placeholder_label):
            raise CrewMovementError("Choose a named person or a placeholder")
        if crew_member_id is not None and quantity != 1:
            raise CrewMovementError("Named passengers have quantity 1")
        passenger = CrewMovementPassenger(
            crew_member_id=crew_member_id,
            placeholder_label=placeholder_label,
            quantity=quantity,
            joining_tentmaster_id=joining_tentmaster_id,
            leaving_tentmaster_id=leaving_tentmaster_id,
        )
        movement.passengers.append(passenger)
        self.session.flush()
        self.validate_capacity(movement)
        self.session.commit()
        return passenger

    def validate_capacity(self, movement: CrewMovement) -> None:
        if movement.van is None:
            return
        count = sum(passenger.quantity for passenger in movement.passengers)
        if count > movement.van.passenger_capacity:
            self.session.rollback()
            raise VanCapacityError(
                f"{movement.movement_code} has {count} passengers for "
                f"{movement.van.passenger_capacity} seats"
            )

    def validate_arrival(self, movement: CrewMovement, work_start: datetime) -> None:
        last_arrival = max((leg.arrive_at for leg in movement.legs), default=movement.arrive_by)
        if last_arrival > work_start:
            raise LateArrivalError("Crew arrives after work starts")

    def passenger_names(self, movement: CrewMovement) -> list[str]:
        names = []
        for passenger in movement.passengers:
            if passenger.crew_member is not None:
                names.append(passenger.crew_member.name)
            else:
                names.append(f"{passenger.quantity} × {passenger.placeholder_label}")
        return names

    def export_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["movement", "route", "departure", "arrival", "passengers", "status"])
        for movement in self.session.query(CrewMovement).order_by(CrewMovement.depart_after):
            writer.writerow(
                [
                    movement.movement_code,
                    f"{movement.origin.name} to {movement.destination.name}",
                    movement.depart_after,
                    movement.arrive_by,
                    ", ".join(self.passenger_names(movement)),
                    movement.status.value,
                ]
            )
        return output.getvalue()

    def _movement(self, movement_id: int) -> CrewMovement:
        movement = self.session.get(CrewMovement, movement_id)
        if movement is None:
            raise CrewMovementError("Crew movement not found")
        return movement


def active_transfer_label(passenger: CrewMovementPassenger) -> str | None:
    if passenger.joining_tentmaster and passenger.leaving_tentmaster:
        return f"{passenger.leaving_tentmaster.name} → {passenger.joining_tentmaster.name}"
    if passenger.joining_tentmaster:
        return f"Joining {passenger.joining_tentmaster.name}"
    if passenger.leaving_tentmaster:
        return f"Leaving {passenger.leaving_tentmaster.name}"
    return None


__all__ = ["CrewMovementService", "CrewMovementError", "JourneyMode", "CrewMember"]
