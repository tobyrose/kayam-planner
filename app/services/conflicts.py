from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.equipment_planning import AllocationStrength, AssignmentStatus, EquipmentAssignment
from app.models.jobs import (
    CommercialStatus,
    Job,
    JobEquipmentRequirement,
    JobPhase,
    RequirementStatus,
)
from app.models.logistics import Load, LoadItem
from app.services.crew_planning import CrewPlanningService
from app.services.jobs import BREAK_TRAIL_DAYS, BUILD_LEAD_DAYS
from app.services.logistics import LogisticsService
from app.services.roster import RosterIndex
from app.services.section_coverage import format_section_shortfall, section_shortfalls


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
        tentmaster_phases = self.session.scalars(
            select(JobPhase)
            .where(JobPhase.tentmaster_id.is_not(None))
            .options(selectinload(JobPhase.job), selectinload(JobPhase.tentmaster))
            .order_by(JobPhase.tentmaster_id, JobPhase.start_at)
        ).all()
        by_tentmaster: dict[int, list[JobPhase]] = {}
        for phase in tentmaster_phases:
            assert phase.tentmaster_id is not None
            by_tentmaster.setdefault(phase.tentmaster_id, []).append(phase)
        for team_phases in by_tentmaster.values():
            for previous_phase, current_phase in zip(team_phases, team_phases[1:], strict=False):
                if previous_phase.end_at > current_phase.start_at:
                    hard = (
                        previous_phase.job.commercial_status == CommercialStatus.CONFIRMED
                        or current_phase.job.commercial_status == CommercialStatus.CONFIRMED
                    )
                    assert current_phase.tentmaster is not None
                    items.append(
                        ConflictItem(
                            "hard" if hard else "conditional",
                            "tentmaster",
                            f"{current_phase.tentmaster.name} double-booked between "
                            f"{previous_phase.job.job_code} and {current_phase.job.job_code}",
                            "/planning",
                        )
                    )
        crew_planning = CrewPlanningService(self.session)
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
            select(JobPhase).options(
                selectinload(JobPhase.job).selectinload(Job.local_crew_bookings)
            )
        ).all()
        roster_index = (
            RosterIndex.build(
                self.session,
                min(phase.start_at for phase in phases),
                max(phase.end_at for phase in phases),
            )
            if phases
            else None
        )
        for phase in phases:
            assert roster_index is not None
            shortfall = crew_planning.phase_headcount(phase, roster_index=roster_index).shortfall
            if shortfall > 0:
                items.append(
                    ConflictItem(
                        "conditional",
                        "crew shortfall",
                        f"{phase.job.job_code} {phase.phase_type.value} is short by {shortfall}",
                        f"/jobs/{phase.job_id}",
                    )
                )
        # Section coverage: required tent sections vs contents of loads arriving at the job site.
        jobs_for_sections = self.session.scalars(
            select(Job).options(
                selectinload(Job.equipment_requirements).selectinload(
                    JobEquipmentRequirement.equipment_type
                ),
                selectinload(Job.tent_requirements),
                selectinload(Job.location),
            )
        ).all()
        all_loads = self.session.scalars(
            select(Load).options(
                selectinload(Load.movement),
                selectinload(Load.items).selectinload(LoadItem.equipment_asset),
                selectinload(Load.items).selectinload(LoadItem.equipment_type),
            )
        ).all()
        for job in jobs_for_sections:
            if not job.tent_requirements:
                continue
            starts = [
                tent.contracted_up_at - timedelta(days=BUILD_LEAD_DAYS)
                for tent in job.tent_requirements
            ]
            ends = [
                tent.contracted_down_at + timedelta(days=BREAK_TRAIL_DAYS)
                for tent in job.tent_requirements
            ]
            window_start, window_end = min(starts), max(ends)
            job_loads = [
                load
                for load in all_loads
                if load.movement.destination_location_id == job.location_id
                and window_start - timedelta(days=3)
                <= load.movement.arrive_by
                <= window_end
            ]
            short = section_shortfalls(job, job_loads)
            if short:
                items.append(
                    ConflictItem(
                        "conditional",
                        "section shortfall",
                        f"{job.job_code}: {format_section_shortfall(short)}",
                        f"/jobs/{job.id}",
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
                and roster_index is not None
                and crew_planning.phase_headcount(phase, roster_index=roster_index).assigned > 0
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
