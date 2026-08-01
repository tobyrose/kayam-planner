from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.crew_planning import CrewAssignment
from app.models.equipment_planning import AllocationStrength, AssignmentStatus, EquipmentAssignment
from app.models.jobs import Job, JobEquipmentRequirement, JobPhase, RequirementStatus
from app.models.logistics import Load, LoadItem
from app.services.logistics import LogisticsService


@dataclass(frozen=True)
class ConflictItem:
    severity: str
    category: str
    message: str
    href: str


@dataclass(frozen=True)
class DirectMovementSuggestion:
    asset_code: str
    origin_id: int
    origin_name: str
    destination_id: int
    destination_name: str
    depart_after: object
    arrive_by: object
    code: str


@dataclass(frozen=True)
class SpareLoadSuggestion:
    load_id: int
    load_code: str
    destination_name: str
    capacity_status: str


class ConflictCentreService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def conflicts(self) -> list[ConflictItem]:
        items: list[ConflictItem] = []
        equipment = self.session.scalars(
            select(EquipmentAssignment)
            .where(EquipmentAssignment.status == AssignmentStatus.ACTIVE)
            .options(
                selectinload(EquipmentAssignment.equipment_asset),
                selectinload(EquipmentAssignment.requirement).selectinload(
                    JobEquipmentRequirement.job
                ),
            )
            .order_by(EquipmentAssignment.equipment_asset_id, EquipmentAssignment.start_at)
        ).all()
        by_asset: dict[int, list[EquipmentAssignment]] = {}
        for assignment in equipment:
            by_asset.setdefault(assignment.equipment_asset_id, []).append(assignment)
        for assignments in by_asset.values():
            for previous, current in zip(assignments, assignments[1:], strict=False):
                if previous.end_at > current.start_at:
                    hard = (
                        previous.allocation_strength == AllocationStrength.HARD
                        or current.allocation_strength == AllocationStrength.HARD
                    )
                    items.append(
                        ConflictItem(
                            "hard" if hard else "conditional",
                            "equipment",
                            f"{current.equipment_asset.asset_code} overlaps "
                            f"{previous.requirement.job.job_code} and "
                            f"{current.requirement.job.job_code}",
                            f"/equipment/{current.equipment_asset_id}",
                        )
                    )
        transported = {
            (item.equipment_asset_id, item.load.movement.destination_location_id)
            for item in self.session.scalars(
                select(LoadItem)
                .where(LoadItem.equipment_asset_id.is_not(None))
                .options(selectinload(LoadItem.load).selectinload(Load.movement))
            )
        }
        for assignment in equipment:
            destination_id = assignment.requirement.job.location_id
            if (
                assignment.equipment_asset.initial_location_id != destination_id
                and (assignment.equipment_asset_id, destination_id) not in transported
            ):
                items.append(
                    ConflictItem(
                        "conditional",
                        "missing transport",
                        f"{assignment.equipment_asset.asset_code} has no load to "
                        f"{assignment.requirement.job.location.name}",
                        f"/jobs/{assignment.requirement.job_id}",
                    )
                )
        crew = self.session.scalars(
            select(CrewAssignment)
            .where(CrewAssignment.crew_member_id.is_not(None))
            .options(
                selectinload(CrewAssignment.crew_member),
                selectinload(CrewAssignment.job_phase).selectinload(JobPhase.job),
            )
            .order_by(CrewAssignment.crew_member_id, CrewAssignment.start_at)
        ).all()
        by_person: dict[int, list[CrewAssignment]] = {}
        for crew_assignment in crew:
            assert crew_assignment.crew_member_id is not None
            by_person.setdefault(crew_assignment.crew_member_id, []).append(crew_assignment)
        for crew_assignments in by_person.values():
            for previous_crew, current_crew in zip(
                crew_assignments, crew_assignments[1:], strict=False
            ):
                if previous_crew.end_at > current_crew.start_at:
                    assert current_crew.crew_member is not None
                    items.append(
                        ConflictItem(
                            "hard",
                            "crew",
                            f"{current_crew.crew_member.name} overlaps "
                            f"{previous_crew.job_phase.job.job_code} and "
                            f"{current_crew.job_phase.job.job_code}",
                            "/planning/crew",
                        )
                    )
        unresolved = self.session.scalars(
            select(JobEquipmentRequirement).where(
                JobEquipmentRequirement.status.in_(
                    [RequirementStatus.UNRESOLVED, RequirementStatus.PARTIALLY_ASSIGNED]
                )
            )
        )
        for requirement in unresolved:
            items.append(
                ConflictItem(
                    "conditional",
                    "equipment requirement",
                    f"{requirement.job.job_code} needs {requirement.quantity_required} × "
                    f"{requirement.equipment_type.code}",
                    f"/jobs/{requirement.job_id}",
                )
            )
        phases = self.session.scalars(
            select(JobPhase).options(selectinload(JobPhase.crew_assignments))
        ).all()
        for phase in phases:
            shortfall = phase.required_headcount - len(phase.crew_assignments)
            if shortfall > 0:
                items.append(
                    ConflictItem(
                        "conditional",
                        "crew shortfall",
                        f"{phase.job.job_code} {phase.phase_type.value} is short by {shortfall}",
                        f"/jobs/{phase.job_id}",
                    )
                )
        logistics = LogisticsService(self.session)
        for load in self.session.scalars(select(Load)):
            capacity = logistics.capacity(load)
            if capacity.status == "over":
                items.append(
                    ConflictItem(
                        "hard",
                        "load capacity",
                        f"{load.display_code} is over capacity",
                        f"/loads/{load.id}",
                    )
                )
            has_receiver = bool(load.movement.destination.receiving_notes) or any(
                phase.job.location_id == load.movement.destination_location_id
                and phase.start_at <= load.movement.arrive_by <= phase.end_at
                and phase.crew_assignments
                for phase in phases
            )
            if not has_receiver:
                items.append(
                    ConflictItem(
                        "conditional",
                        "receiving warning",
                        f"{load.display_code} has no recorded receiver at "
                        f"{load.movement.destination.name}",
                        f"/loads/{load.id}",
                    )
                )
        return items

    def direct_movement_suggestions(self) -> list[DirectMovementSuggestion]:
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
        suggestions = []
        for asset_assignments in grouped.values():
            for previous, current in zip(asset_assignments, asset_assignments[1:], strict=False):
                origin = previous.requirement.job.location
                destination = current.requirement.job.location
                if origin.id == destination.id or previous.end_at >= current.start_at:
                    continue
                suggestions.append(
                    DirectMovementSuggestion(
                        current.equipment_asset.asset_code,
                        origin.id,
                        origin.name,
                        destination.id,
                        destination.name,
                        previous.end_at,
                        current.start_at,
                        f"SUG-{current.equipment_asset.asset_code}-{previous.id}-{current.id}",
                    )
                )
        return suggestions

    def spare_load_suggestions(self) -> list[SpareLoadSuggestion]:
        logistics = LogisticsService(self.session)
        return [
            SpareLoadSuggestion(
                load.id,
                load.display_code,
                load.movement.destination.name,
                logistics.capacity(load).status,
            )
            for load in self.session.scalars(select(Load))
            if logistics.capacity(load).status in {"within", "near"}
            and load.movement.arrive_by - load.movement.depart_after <= timedelta(days=3)
        ]
