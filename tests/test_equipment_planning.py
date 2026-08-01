from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import EquipmentAsset
from app.models.equipment_planning import AllocationStrength
from app.models.jobs import Job, JobEquipmentRequirement
from app.services.equipment_planning import (
    EquipmentPlanningService,
    HardAllocationConflictError,
    IncompatibleEquipmentError,
    LockedAssignmentError,
)


def seeded_requirements(
    session: Session,
) -> tuple[
    EquipmentPlanningService, EquipmentAsset, JobEquipmentRequirement, JobEquipmentRequirement
]:
    seed_development_data(session)
    service = EquipmentPlanningService(session)
    asset = session.scalar(select(EquipmentAsset).where(EquipmentAsset.asset_code == "K1"))
    roskilde = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    scotland = session.scalar(select(Job).where(Job.job_code == "DEMO-SCO-26"))
    assert asset is not None and roskilde is not None and scotland is not None
    first = next(
        item for item in roskilde.equipment_requirements if item.equipment_type.code == "END"
    )
    second = next(
        item for item in scotland.equipment_requirements if item.equipment_type.code == "END"
    )
    return service, asset, first, second


def allocation_payload(
    asset: EquipmentAsset,
    requirement: JobEquipmentRequirement,
    strength: str,
    *,
    start_at: object | None = None,
    end_at: object | None = None,
    locked: bool = False,
) -> dict[str, object]:
    return {
        "job_equipment_requirement_id": requirement.id,
        "equipment_asset_id": asset.id,
        "start_at": start_at or requirement.required_on_site_at,
        "end_at": end_at or requirement.releasable_at,
        "allocation_strength": strength,
        "assignment_source": "manual",
        "locked": locked,
        "status": "active",
    }


def test_hard_overlap_is_blocked(session: Session) -> None:
    service, asset, first, second = seeded_requirements(session)
    first_assignment = service.assign(allocation_payload(asset, first, "hard"))

    with pytest.raises(HardAllocationConflictError):
        service.assign(
            allocation_payload(
                asset,
                second,
                "hard",
                start_at=first_assignment.start_at,
                end_at=first_assignment.end_at,
            )
        )


def test_soft_competition_is_allowed_and_reported(session: Session) -> None:
    service, asset, first, second = seeded_requirements(session)
    first_assignment = service.assign(allocation_payload(asset, first, "soft"))
    second_assignment = service.assign(
        allocation_payload(
            asset,
            second,
            "soft",
            start_at=first_assignment.start_at,
            end_at=first_assignment.end_at,
        )
    )

    conflicts = service.conflicts_for(
        asset.id,
        second_assignment.start_at,
        second_assignment.end_at,
        exclude_id=second_assignment.id,
    )
    assert conflicts[0].severity == "conditional"


def test_incompatible_asset_is_rejected(session: Session) -> None:
    seed_development_data(session)
    service = EquipmentPlanningService(session)
    asset = session.scalar(select(EquipmentAsset).where(EquipmentAsset.asset_code == "K1"))
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    assert asset is not None and job is not None
    pole_requirement = next(
        item for item in job.equipment_requirements if item.equipment_type.code == "POLE"
    )

    with pytest.raises(IncompatibleEquipmentError):
        service.assign(allocation_payload(asset, pole_requirement, "soft"))


def test_locked_assignment_survives_automatic_update(session: Session) -> None:
    service, asset, first, _ = seeded_requirements(session)
    assignment = service.assign(allocation_payload(asset, first, "soft", locked=True))

    with pytest.raises(LockedAssignmentError):
        service.update_assignment(
            assignment.id,
            allocation_payload(asset, first, "soft", locked=True),
            automatic=True,
        )


def test_asset_state_and_confirmation_workflow(session: Session) -> None:
    service, asset, first, _ = seeded_requirements(session)
    assignment = service.assign(allocation_payload(asset, first, "soft"))
    assert service.derive_state(assignment, first.job.must_be_up_at) == "in_use"

    job = service.confirm_job(first.job_id, [assignment.id])
    assert assignment.allocation_strength == AllocationStrength.HARD
    assert assignment.locked is True
    assert job.commercial_status.value == "confirmed"
