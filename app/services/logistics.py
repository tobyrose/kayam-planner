from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.administration import EquipmentAsset
from app.models.equipment_planning import AssignmentStatus, EquipmentAssignment
from app.models.jobs import Job, JobEquipmentRequirement, RecordSource
from app.models.logistics import EquipmentMovement, Load, LoadItem, LoadStatus
from app.schemas.logistics import LoadData, LoadItemData, MovementData


class LogisticsError(Exception):
    pass


class LockedLoadError(LogisticsError):
    pass


class LocationContinuityError(LogisticsError):
    pass


@dataclass(frozen=True)
class CapacityUse:
    section_units: Decimal
    pole_units: Decimal
    ancillary_units: Decimal
    weight_kg: Decimal
    section_percent: Decimal | None
    pole_percent: Decimal | None
    ancillary_percent: Decimal | None
    weight_percent: Decimal | None
    status: str


def _percent(used: Decimal, capacity: Decimal) -> Decimal | None:
    if capacity <= 0:
        return None if used == 0 else Decimal("999")
    return (used / capacity * 100).quantize(Decimal("0.1"))


class LogisticsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_movement(self, payload: dict[str, Any]) -> EquipmentMovement:
        movement = EquipmentMovement(**MovementData.model_validate(payload).model_dump())
        self.session.add(movement)
        self._commit_unique("Movement code already exists")
        self.session.refresh(movement)
        return movement

    def create_load(self, payload: dict[str, Any]) -> Load:
        values = LoadData.model_validate(payload).model_dump()
        movement = self.session.get(EquipmentMovement, values["equipment_movement_id"])
        if movement is None:
            raise LogisticsError("Movement not found")
        if movement.locked:
            raise LockedLoadError("Locked movements cannot receive new loads")
        load = Load(**values)
        self.session.add(load)
        self._commit_unique("Load number must be unique within the movement")
        self.session.refresh(load)
        return load

    def generate_movement_requirements(self) -> list[EquipmentMovement]:
        """Create unlocked requirements for unexplained transitions, preserving existing plans."""
        assignments = self.session.scalars(
            select(EquipmentAssignment)
            .where(EquipmentAssignment.status == AssignmentStatus.ACTIVE)
            .options(
                selectinload(EquipmentAssignment.equipment_asset),
                selectinload(EquipmentAssignment.requirement)
                .selectinload(JobEquipmentRequirement.job)
                .selectinload(Job.location),
            )
            .order_by(EquipmentAssignment.equipment_asset_id, EquipmentAssignment.start_at)
        ).all()
        grouped: dict[int, list[EquipmentAssignment]] = {}
        for assignment in assignments:
            grouped.setdefault(assignment.equipment_asset_id, []).append(assignment)
        created = []
        for asset_assignments in grouped.values():
            for previous, current in zip(asset_assignments, asset_assignments[1:], strict=False):
                origin = previous.requirement.job.location
                destination = current.requirement.job.location
                if origin.id == destination.id or previous.end_at >= current.start_at:
                    continue
                code = f"REQ-{current.equipment_asset.asset_code}-{previous.id}-{current.id}"
                exists = self.session.scalar(
                    select(EquipmentMovement.id).where(EquipmentMovement.movement_code == code)
                )
                if exists is not None:
                    continue
                movement = EquipmentMovement(
                    movement_code=code,
                    origin_location_id=origin.id,
                    destination_location_id=destination.id,
                    depart_after=previous.end_at,
                    arrive_by=current.start_at,
                    source=RecordSource.GENERATED,
                )
                self.session.add(movement)
                created.append(movement)
        self.session.commit()
        return created

    def add_item(self, payload: dict[str, Any], *, automatic: bool = False) -> LoadItem:
        values = LoadItemData.model_validate(payload).model_dump()
        load = self.session.get(Load, values["load_id"])
        if load is None:
            raise LogisticsError("Load not found")
        if load.locked:
            raise LockedLoadError("Locked loads cannot be changed")
        asset_id = values["equipment_asset_id"]
        if asset_id is not None:
            self.validate_asset_continuity(asset_id, load)
        values.pop("load_id")
        item = LoadItem(**values)
        load.items.append(item)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise LogisticsError("That asset is already on this load") from error
        self.session.refresh(item)
        return item

    def capacity(self, load: Load) -> CapacityUse:
        used = [Decimal(0), Decimal(0), Decimal(0), Decimal(0)]
        for item in load.items:
            equipment_type = item.resolved_type
            quantity = Decimal(item.quantity)
            used[0] += equipment_type.section_capacity_units * quantity
            used[1] += equipment_type.pole_capacity_units * quantity
            used[2] += equipment_type.ancillary_capacity_units * quantity
            used[3] += equipment_type.weight_kg * quantity
        capacity = load.lorry_type
        percentages = (
            _percent(used[0], capacity.section_capacity_units),
            _percent(used[1], capacity.pole_capacity_units),
            _percent(used[2], capacity.ancillary_capacity_units),
            _percent(used[3], capacity.payload_kg),
        )
        measured = [value for value in percentages if value is not None]
        maximum = max(measured, default=Decimal(0))
        status = "over" if maximum > 100 else "near" if maximum >= 85 else "within"
        return CapacityUse(
            section_units=used[0],
            pole_units=used[1],
            ancillary_units=used[2],
            weight_kg=used[3],
            section_percent=percentages[0],
            pole_percent=percentages[1],
            ancillary_percent=percentages[2],
            weight_percent=percentages[3],
            status=status,
        )

    def validate_asset_continuity(self, asset_id: int, target_load: Load) -> None:
        asset = self.session.get(EquipmentAsset, asset_id)
        if asset is None:
            raise LogisticsError("Asset not found")
        previous = self.session.scalar(
            select(Load)
            .join(LoadItem)
            .join(Load.movement)
            .where(
                LoadItem.equipment_asset_id == asset_id,
                EquipmentMovement.arrive_by <= target_load.movement.depart_after,
            )
            .order_by(EquipmentMovement.arrive_by.desc())
            .limit(1)
        )
        expected_location_id = (
            previous.movement.destination_location_id
            if previous is not None
            else asset.initial_location_id
        )
        if (
            expected_location_id is not None
            and expected_location_id != target_load.movement.origin_location_id
        ):
            raise LocationContinuityError(
                f"{asset.asset_code} is expected at another location before this movement"
            )

    def set_status(self, load_id: int, status: str) -> Load:
        load = self.session.get(Load, load_id)
        if load is None:
            raise LogisticsError("Load not found")
        if load.locked:
            raise LockedLoadError("Locked loads cannot be changed")
        load.status = LoadStatus(status)
        self.session.commit()
        return load

    def export_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["load", "status", "origin", "destination", "departure", "arrival", "capacity"]
        )
        loads = self.session.scalars(
            select(Load).join(Load.movement).order_by(EquipmentMovement.depart_after)
        )
        for load in loads:
            writer.writerow(
                [
                    load.display_code,
                    load.status.value,
                    load.movement.origin.name,
                    load.movement.destination.name,
                    load.planned_departure_at or load.movement.depart_after,
                    load.planned_arrival_at or load.movement.arrive_by,
                    self.capacity(load).status,
                ]
            )
        return output.getvalue()

    def _commit_unique(self, message: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise LogisticsError(message) from error
