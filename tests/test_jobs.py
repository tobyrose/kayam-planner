from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import (
    BuildStage,
    EquipmentLink,
    EquipmentType,
    Location,
    Tentmaster,
)
from app.models.jobs import (
    JobEquipmentRequirement,
    PhaseType,
    RequirementSource,
    RequirementStatus,
)
from app.schemas.jobs import JobData
from app.services.jobs import JobError, JobService

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
        "site_clear_by": datetime(2026, 6, 8, 18, tzinfo=LONDON),
        "maintenance_cover_required": True,
    }


def test_job_date_validation_rejects_reversed_milestones(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    payload = job_payload(location.id)
    payload["site_clear_by"] = datetime(2026, 5, 31, 20, tzinfo=LONDON)

    with pytest.raises(ValidationError, match="Site access must be before"):
        JobData.model_validate(payload)


def test_kmmmk_sequence_expands_sections_and_derived_poles(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id))

    service.add_tent_requirement(job.id, {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": datetime(2026, 6, 1, 8, tzinfo=LONDON),
            "contracted_down_at": datetime(2026, 6, 5, 8, tzinfo=LONDON),
        })

    quantities = {
        requirement.equipment_type.code: requirement.quantity_required
        for requirement in job.equipment_requirements
    }
    assert quantities["K"] == 2
    assert quantities["M"] == 3
    # 5 sections * 2 - 2 = 8 physical poles, pack_size 2 per P asset -> 4 P assets.
    assert quantities["P"] == 4


def test_linked_equipment_cascades_from_sections_and_poles(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id))

    service.add_tent_requirement(job.id, {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": datetime(2026, 6, 1, 8, tzinfo=LONDON),
            "contracted_down_at": datetime(2026, 6, 5, 8, tzinfo=LONDON),
        })

    quantities = {
        requirement.equipment_type.code: requirement.quantity_required
        for requirement in job.equipment_requirements
    }
    assert quantities["BALE_RING"] == 8  # 3 M * 2 per M + 2 K * 1 per K (kay.parts.csv)
    assert quantities["SIDE_GUY"] == 8  # 4 P * 2 per P
    assert quantities["TIFOR_1_5T"] == 8  # 4 P * 2 per P


def test_requirement_expansion_multiplies_and_preserves_manual_items(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    ancillary = session.scalar(select(EquipmentType).where(EquipmentType.code == "CT"))
    assert location is not None and ancillary is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id, "JOB-002"))
    manual = JobEquipmentRequirement(
        job_id=job.id,
        equipment_type_id=ancillary.id,
        quantity_required=7,
        required_on_site_at=datetime(2026, 6, 1, 8, tzinfo=LONDON),
        releasable_at=datetime(2026, 6, 8, 8, tzinfo=LONDON),
        required_stage=BuildStage.MAINTENANCE,
        source=RequirementSource.MANUAL,
        status=RequirementStatus.UNRESOLVED,
        notes="Planner-added extra",
    )
    session.add(manual)
    session.commit()

    service.add_tent_requirement(job.id, {
            "sequence": "K-M-M-K",
            "quantity": 2,
            "contracted_up_at": datetime(2026, 6, 1, 8, tzinfo=LONDON),
            "contracted_down_at": datetime(2026, 6, 5, 8, tzinfo=LONDON),
        })
    service.regenerate_requirements(job)
    session.commit()

    quantities = {
        (requirement.equipment_type.code, requirement.required_stage): requirement.quantity_required
        for requirement in job.equipment_requirements
    }
    assert quantities[("K", BuildStage.MAIN_SECTIONS)] == 4
    assert quantities[("M", BuildStage.MAIN_SECTIONS)] == 4
    # 4 sections * 2 - 2 = 6 poles / pack_size 2 = 3 P per tent * 2 tents = 6.
    assert quantities[("P", BuildStage.POLES_AND_ANCHORS)] == 6
    assert session.get(JobEquipmentRequirement, manual.id) is not None
    assert manual.quantity_required == 7


def test_add_tent_requirement_rejects_unknown_code(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id))

    with pytest.raises(JobError, match="Unknown section code"):
        service.add_tent_requirement(job.id, {
            "sequence": "K-ZZ-K",
            "quantity": 1,
            "contracted_up_at": datetime(2026, 6, 1, 8, tzinfo=LONDON),
            "contracted_down_at": datetime(2026, 6, 5, 8, tzinfo=LONDON),
        })


def test_add_tent_requirement_rejects_non_section_code(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id))

    with pytest.raises(JobError, match="Not a bookable section type"):
        service.add_tent_requirement(job.id, {
            "sequence": "K-P-K",
            "quantity": 1,
            "contracted_up_at": datetime(2026, 6, 1, 8, tzinfo=LONDON),
            "contracted_down_at": datetime(2026, 6, 5, 8, tzinfo=LONDON),
        })


def test_add_tent_requirement_rejects_mixed_family(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id))

    with pytest.raises(JobError, match="same tent family"):
        service.add_tent_requirement(job.id, {
            "sequence": "K-V-K",
            "quantity": 1,
            "contracted_up_at": datetime(2026, 6, 1, 8, tzinfo=LONDON),
            "contracted_down_at": datetime(2026, 6, 5, 8, tzinfo=LONDON),
        })


def test_expansion_guards_against_indirect_equipment_link_cycle(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    m_type = session.scalar(select(EquipmentType).where(EquipmentType.code == "M"))
    bale_ring = session.scalar(select(EquipmentType).where(EquipmentType.code == "BALE_RING"))
    assert location is not None and m_type is not None and bale_ring is not None
    # Indirect cycle: M -> BALE_RING (already seeded) and BALE_RING -> M (added here).
    session.add(
        EquipmentLink(
            parent_equipment_type_id=bale_ring.id,
            child_equipment_type_id=m_type.id,
            quantity_per_parent=1,
        )
    )
    session.commit()
    service = JobService(session)
    job = service.create_job(job_payload(location.id))

    service.add_tent_requirement(job.id, {
            "sequence": "K-M-K",
            "quantity": 1,
            "contracted_up_at": datetime(2026, 6, 1, 8, tzinfo=LONDON),
            "contracted_down_at": datetime(2026, 6, 5, 8, tzinfo=LONDON),
        })

    quantities = {
        requirement.equipment_type.code: requirement.quantity_required
        for requirement in job.equipment_requirements
    }
    # 1 direct (the M section itself) + 1 per K section via K -> BALE_RING -> M (kay.parts.csv
    # added a real K -> BALE_RING link) — each K-rooted traversal has its own fresh `visited` set,
    # so the cycle guard only stops M from re-entering its *own* traversal, not a different
    # section's. The guard still does its job: BALE_RING -> M -> BALE_RING never recurses forever.
    assert quantities["M"] == 3
    # 2 K * 1 per K + 1 M (direct) * 2 per M = 4.
    assert quantities["BALE_RING"] == 4


def test_first_tent_seeds_build_up_break(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id, "JOB-003"))
    up = datetime(2026, 6, 10, 8, tzinfo=LONDON)
    down = datetime(2026, 6, 15, 8, tzinfo=LONDON)
    requirement = service.add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": up,
            "contracted_down_at": down,
        },
    )

    phase_types = {phase.phase_type for phase in job.phases}
    assert phase_types == {PhaseType.BUILD, PhaseType.UP, PhaseType.BREAK}
    build = next(phase for phase in job.phases if phase.phase_type == PhaseType.BUILD)
    up_phase = next(phase for phase in job.phases if phase.phase_type == PhaseType.UP)
    brk = next(phase for phase in job.phases if phase.phase_type == PhaseType.BREAK)
    assert build.start_at == up - timedelta(days=5)
    assert build.end_at == up
    assert up_phase.start_at == up
    assert up_phase.end_at == down
    assert up_phase.job_tent_requirement_id == requirement.id
    assert brk.start_at == down
    assert brk.end_at == down + timedelta(days=3)


def test_second_tent_with_later_up_seeds_extra_build_segment(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id, "JOB-003B"))
    first_up = datetime(2026, 6, 10, 8, tzinfo=LONDON)
    service.add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": first_up,
            "contracted_down_at": datetime(2026, 6, 15, 8, tzinfo=LONDON),
        },
    )
    second_up = datetime(2026, 6, 12, 8, tzinfo=LONDON)
    service.add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-K",
            "quantity": 1,
            "contracted_up_at": second_up,
            "contracted_down_at": datetime(2026, 6, 16, 8, tzinfo=LONDON),
        },
    )

    build_phases = [phase for phase in job.phases if phase.phase_type == PhaseType.BUILD]
    assert len(build_phases) == 2
    extra_build = next(phase for phase in build_phases if phase.start_at == first_up)
    assert extra_build.end_at == second_up


def test_up_phase_cannot_extend_outside_tent_contract_window(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert location is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id, "JOB-003C"))
    up = datetime(2026, 6, 10, 8, tzinfo=LONDON)
    down = datetime(2026, 6, 15, 8, tzinfo=LONDON)
    service.add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": up,
            "contracted_down_at": down,
        },
    )
    up_phase = next(phase for phase in job.phases if phase.phase_type == PhaseType.UP)

    with pytest.raises(JobError, match="contract window"):
        service.update_phase(
            job.id,
            up_phase.id,
            {
                "phase_type": "up",
                "job_tent_requirement_id": up_phase.job_tent_requirement_id,
                "tentmaster_id": None,
                "start_at": up - timedelta(hours=1),
                "end_at": down,
                "required_headcount": 0,
                "locked": False,
                "source": "manual",
            },
        )


def test_reassign_phase_tentmaster_moves_phase_between_teams(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    tentmaster = session.scalar(select(Tentmaster))
    assert location is not None and tentmaster is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id, "JOB-004"))
    service.add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": datetime(2026, 6, 1, 8, tzinfo=LONDON),
            "contracted_down_at": datetime(2026, 6, 5, 8, tzinfo=LONDON),
        },
    )
    phase = job.phases[0]
    assert phase.tentmaster_id is None

    JobService(session).reassign_phase_tentmaster(phase.id, tentmaster.id)
    session.refresh(phase)
    assert phase.tentmaster_id == tentmaster.id

    JobService(session).reassign_phase_tentmaster(phase.id, None)
    session.refresh(phase)
    assert phase.tentmaster_id is None


def test_reassign_phase_tentmaster_rejects_locked_phase(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    tentmaster = session.scalar(select(Tentmaster))
    assert location is not None and tentmaster is not None
    service = JobService(session)
    job = service.create_job(job_payload(location.id, "JOB-005"))
    service.add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": datetime(2026, 6, 1, 8, tzinfo=LONDON),
            "contracted_down_at": datetime(2026, 6, 5, 8, tzinfo=LONDON),
        },
    )
    phase = job.phases[0]
    phase.locked = True
    session.commit()

    with pytest.raises(JobError, match="locked"):
        JobService(session).reassign_phase_tentmaster(phase.id, tentmaster.id)
