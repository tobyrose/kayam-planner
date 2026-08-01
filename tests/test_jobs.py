from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import BuildStage, EquipmentType, Location, TentConfiguration
from app.models.jobs import (
    JobEquipmentRequirement,
    PhaseType,
    RequirementSource,
    RequirementStatus,
)
from app.schemas.jobs import JobData
from app.services.jobs import JobService

LONDON = ZoneInfo("Europe/London")


def job_payload(location_id: int, code: str = "JOB-001") -> dict[str, object]:
    return {
        "job_code": code,
        "name": "Test event",
        "customer_name": "Test customer",
        "location_id": location_id,
        "commercial_status": "enquiry",
        "planning_status": "not_planned",
        "confidence_percent": 50,
        "contract_revenue": "10000",
        "currency": "GBP",
        "site_access_at": datetime(2026, 6, 1, 8, tzinfo=LONDON),
        "must_be_up_at": datetime(2026, 6, 3, 20, tzinfo=LONDON),
        "show_start_at": datetime(2026, 6, 4, 10, tzinfo=LONDON),
        "show_end_at": datetime(2026, 6, 6, 23, tzinfo=LONDON),
        "strike_available_at": datetime(2026, 6, 7, 8, tzinfo=LONDON),
        "site_clear_by": datetime(2026, 6, 8, 18, tzinfo=LONDON),
        "maintenance_cover_required": True,
        "local_crew_supplied": 0,
        "local_crew_required": 0,
    }


def test_job_date_validation_rejects_reversed_milestones(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    payload = job_payload(location.id)
    payload["must_be_up_at"] = datetime(2026, 5, 31, 20, tzinfo=LONDON)

    with pytest.raises(ValidationError, match="Site access must be before"):
        JobData.model_validate(payload)


def test_ten_pole_requirement_expands_from_configuration(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    configuration = session.scalar(
        select(TentConfiguration).where(TentConfiguration.name == "Kayam 10-pole")
    )
    assert location is not None and configuration is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id))

    service.add_tent_requirement(
        job.id,
        {"tent_configuration_id": configuration.id, "quantity": 1},
    )

    quantities = {
        requirement.equipment_type.code: requirement.quantity_required
        for requirement in job.equipment_requirements
    }
    assert quantities["END"] == 2
    assert quantities["MIDDLE"] == 4
    assert quantities["POLE"] == 10


def test_requirement_expansion_multiplies_and_preserves_manual_items(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    configuration = session.scalar(
        select(TentConfiguration).where(TentConfiguration.name == "Kayam 6-pole")
    )
    ancillary = session.scalar(select(EquipmentType).where(EquipmentType.code == "ANCILLARY_KIT"))
    assert location is not None and configuration is not None and ancillary is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id, "JOB-002"))
    manual = JobEquipmentRequirement(
        job_id=job.id,
        equipment_type_id=ancillary.id,
        quantity_required=7,
        required_on_site_at=job.site_access_at,
        releasable_at=job.strike_available_at,
        required_stage=BuildStage.MAINTENANCE,
        source=RequirementSource.MANUAL,
        status=RequirementStatus.UNRESOLVED,
        notes="Planner-added extra",
    )
    session.add(manual)
    session.commit()

    service.add_tent_requirement(
        job.id,
        {"tent_configuration_id": configuration.id, "quantity": 2},
    )
    service.regenerate_requirements(job)
    session.commit()

    quantities = {
        (requirement.equipment_type.code, requirement.required_stage): requirement.quantity_required
        for requirement in job.equipment_requirements
    }
    assert quantities[("END", BuildStage.MAIN_SECTIONS)] == 4
    assert quantities[("MIDDLE", BuildStage.MAIN_SECTIONS)] == 4
    assert quantities[("POLE", BuildStage.POLES_AND_ANCHORS)] == 12
    assert session.get(JobEquipmentRequirement, manual.id) is not None
    assert manual.quantity_required == 7


def test_phase_generation_creates_build_show_maintenance_and_strike(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    job = JobService(session).create_job(job_payload(location.id, "JOB-003"))

    phase_types = {phase.phase_type for phase in job.phases}
    assert phase_types == {
        PhaseType.BUILD,
        PhaseType.SHOW,
        PhaseType.MAINTENANCE,
        PhaseType.STRIKE,
    }
    build = next(phase for phase in job.phases if phase.phase_type == PhaseType.BUILD)
    assert build.start_at == job.site_access_at
    assert build.end_at == job.must_be_up_at
