from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.administration import EquipmentAsset
from app.models.equipment_planning import (
    AllocationStrength,
    AssignmentStatus,
    EquipmentAssignment,
    EquipmentCompatibility,
)
from app.models.jobs import (
    CommercialStatus,
    Job,
    JobEquipmentRequirement,
    PlanningStatus,
    RequirementStatus,
)
from app.schemas.equipment_planning import EquipmentAssignmentData


class EquipmentPlanningError(Exception):
    pass


class IncompatibleEquipmentError(EquipmentPlanningError):
    pass


class HardAllocationConflictError(EquipmentPlanningError):
    pass


class LockedAssignmentError(EquipmentPlanningError):
    pass


@dataclass(frozen=True)
class EquipmentConflict:
    severity: str
    message: str
    assignment_id: int


@dataclass(frozen=True)
class AssetTimelineEntry:
    start_at: datetime
    end_at: datetime
    state: str
    job_id: int
    job_name: str
    location_name: str
    allocation_strength: str
    locked: bool


class EquipmentPlanningService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def is_compatible(self, asset: EquipmentAsset, requirement: JobEquipmentRequirement) -> bool:
        if asset.equipment_type_id == requirement.equipment_type_id:
            return True
        compatibility = self.session.scalar(
            select(EquipmentCompatibility.id).where(
                EquipmentCompatibility.required_equipment_type_id == requirement.equipment_type_id,
                EquipmentCompatibility.compatible_equipment_type_id == asset.equipment_type_id,
                EquipmentCompatibility.active,
            )
        )
        return compatibility is not None

    def conflicts_for(
        self,
        asset_id: int,
        start_at: datetime,
        end_at: datetime,
        *,
        exclude_id: int | None = None,
    ) -> list[EquipmentConflict]:
        query = select(EquipmentAssignment).where(
            EquipmentAssignment.equipment_asset_id == asset_id,
            EquipmentAssignment.status == AssignmentStatus.ACTIVE,
            EquipmentAssignment.start_at < end_at,
            EquipmentAssignment.end_at > start_at,
        )
        if exclude_id is not None:
            query = query.where(EquipmentAssignment.id != exclude_id)
        conflicts = []
        for assignment in self.session.scalars(query):
            severity = (
                "hard"
                if assignment.allocation_strength == AllocationStrength.HARD
                else "conditional"
            )
            conflicts.append(
                EquipmentConflict(
                    severity,
                    f"{assignment.equipment_asset.asset_code} is allocated to "
                    f"{assignment.requirement.job.name}",
                    assignment.id,
                )
            )
        return conflicts

    def assign(self, payload: dict[str, Any]) -> EquipmentAssignment:
        values = EquipmentAssignmentData.model_validate(payload).model_dump()
        requirement = self.session.get(
            JobEquipmentRequirement, values["job_equipment_requirement_id"]
        )
        asset = self.session.get(EquipmentAsset, values["equipment_asset_id"])
        if requirement is None or asset is None:
            raise EquipmentPlanningError("Requirement or asset not found")
        if not asset.active or not asset.serviceable:
            raise IncompatibleEquipmentError("Asset is inactive or unserviceable")
        if not self.is_compatible(asset, requirement):
            raise IncompatibleEquipmentError(
                f"{asset.asset_code} is not compatible with {requirement.equipment_type.code}"
            )
        conflicts = self.conflicts_for(asset.id, values["start_at"], values["end_at"])
        if values["allocation_strength"] == AllocationStrength.HARD and conflicts:
            raise HardAllocationConflictError("; ".join(item.message for item in conflicts))
        assignment = EquipmentAssignment(**values)
        self.session.add(assignment)
        self.session.flush()
        self._update_requirement_status(requirement)
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def update_assignment(
        self, assignment_id: int, payload: dict[str, Any], *, automatic: bool = False
    ) -> EquipmentAssignment:
        assignment = self.session.get(EquipmentAssignment, assignment_id)
        if assignment is None:
            raise EquipmentPlanningError("Assignment not found")
        if automatic and assignment.locked:
            raise LockedAssignmentError("Locked assignments cannot be changed automatically")
        values = EquipmentAssignmentData.model_validate(payload).model_dump()
        conflicts = self.conflicts_for(
            values["equipment_asset_id"],
            values["start_at"],
            values["end_at"],
            exclude_id=assignment.id,
        )
        if values["allocation_strength"] == AllocationStrength.HARD and conflicts:
            raise HardAllocationConflictError("; ".join(item.message for item in conflicts))
        for key, value in values.items():
            setattr(assignment, key, value)
        self.session.commit()
        return assignment

    def candidates(self, requirement: JobEquipmentRequirement) -> list[EquipmentAsset]:
        compatible_ids = select(EquipmentCompatibility.compatible_equipment_type_id).where(
            EquipmentCompatibility.required_equipment_type_id == requirement.equipment_type_id,
            EquipmentCompatibility.active,
        )
        hard_overlap = select(EquipmentAssignment.equipment_asset_id).where(
            EquipmentAssignment.allocation_strength == AllocationStrength.HARD,
            EquipmentAssignment.status == AssignmentStatus.ACTIVE,
            EquipmentAssignment.start_at < requirement.releasable_at,
            EquipmentAssignment.end_at > requirement.required_on_site_at,
        )
        return list(
            self.session.scalars(
                select(EquipmentAsset)
                .where(
                    EquipmentAsset.active,
                    EquipmentAsset.serviceable,
                    or_(
                        EquipmentAsset.equipment_type_id == requirement.equipment_type_id,
                        EquipmentAsset.equipment_type_id.in_(compatible_ids),
                    ),
                    EquipmentAsset.id.not_in(hard_overlap),
                )
                .order_by(
                    EquipmentAsset.initial_location_id != requirement.job.location_id,
                    EquipmentAsset.asset_code,
                )
            ).all()
        )

    def confirm_job(
        self, job_id: int, approved_assignment_ids: list[int], *, lock: bool = True
    ) -> Job:
        job = self.session.get(Job, job_id)
        if job is None:
            raise EquipmentPlanningError("Job not found")
        assignments = list(
            self.session.scalars(
                select(EquipmentAssignment)
                .join(EquipmentAssignment.requirement)
                .where(
                    JobEquipmentRequirement.job_id == job.id,
                    EquipmentAssignment.id.in_(approved_assignment_ids),
                )
            ).all()
        )
        for assignment in assignments:
            conflicts = self.conflicts_for(
                assignment.equipment_asset_id,
                assignment.start_at,
                assignment.end_at,
                exclude_id=assignment.id,
            )
            if conflicts:
                raise HardAllocationConflictError("; ".join(item.message for item in conflicts))
        for assignment in assignments:
            assignment.allocation_strength = AllocationStrength.HARD
            assignment.locked = lock
        job.commercial_status = CommercialStatus.CONFIRMED
        job.planning_status = PlanningStatus.PLANNER_APPROVED
        self.session.commit()
        return job

    def timeline(self, asset_id: int) -> list[AssetTimelineEntry]:
        assignments = self.session.scalars(
            select(EquipmentAssignment)
            .where(
                EquipmentAssignment.equipment_asset_id == asset_id,
                EquipmentAssignment.status == AssignmentStatus.ACTIVE,
            )
            .order_by(EquipmentAssignment.start_at)
        ).all()
        return [
            AssetTimelineEntry(
                assignment.start_at,
                assignment.end_at,
                self.derive_state(assignment),
                assignment.requirement.job.id,
                assignment.requirement.job.name,
                assignment.requirement.job.location.name,
                assignment.allocation_strength.value,
                assignment.locked,
            )
            for assignment in assignments
        ]

    @staticmethod
    def derive_state(assignment: EquipmentAssignment, at: datetime | None = None) -> str:
        at = at or assignment.start_at
        job = assignment.requirement.job
        if at < job.site_access_at:
            return "allocated"
        build_phase = next(
            (phase for phase in job.phases if phase.phase_type.value == "build"), None
        )
        strike_phase = next(
            (phase for phase in job.phases if phase.phase_type.value == "strike"), None
        )
        if build_phase and build_phase.start_at <= at < build_phase.end_at:
            return "building"
        if strike_phase and strike_phase.start_at <= at < strike_phase.end_at:
            return "striking"
        if job.must_be_up_at <= at < job.strike_available_at:
            return "in_use"
        return "waiting"

    @staticmethod
    def _update_requirement_status(requirement: JobEquipmentRequirement) -> None:
        active_count = sum(
            1 for item in requirement.assignments if item.status == AssignmentStatus.ACTIVE
        )
        if active_count == 0:
            requirement.status = RequirementStatus.UNRESOLVED
        elif active_count < requirement.quantity_required:
            requirement.status = RequirementStatus.PARTIALLY_ASSIGNED
        else:
            requirement.status = RequirementStatus.ASSIGNED
