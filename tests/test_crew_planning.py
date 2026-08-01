from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import (
    CrewAvailability,
    CrewAvailabilityStatus,
    CrewMember,
    Tentmaster,
)
from app.models.jobs import Job, PhaseType
from app.services.crew_planning import CrewHardConflictError, CrewPlanningService


def seeded_phase_and_person(session: Session) -> tuple[Job, object, CrewMember, Tentmaster]:
    seed_development_data(session)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert job is not None and person is not None and team is not None
    phase = next(item for item in job.phases if item.phase_type == PhaseType.BUILD)
    return job, phase, person, team


def assignment_payload(phase: object, person: CrewMember, team: Tentmaster) -> dict[str, object]:
    return {
        "job_phase_id": phase.id,
        "crew_member_id": person.id,
        "placeholder_name": None,
        "tentmaster_id": team.id,
        "start_at": phase.start_at,
        "end_at": phase.end_at,
        "role": "Crew",
        "assignment_source": "manual",
        "locked": False,
    }


def test_named_crew_overlap_on_confirmed_work_is_blocked(session: Session) -> None:
    _, phase, person, team = seeded_phase_and_person(session)
    service = CrewPlanningService(session)
    payload = assignment_payload(phase, person, team)
    service.assign(payload)

    with pytest.raises(CrewHardConflictError, match="Overlaps"):
        service.assign(payload)


def test_crew_unavailability_blocks_confirmed_assignment(session: Session) -> None:
    _, phase, person, team = seeded_phase_and_person(session)
    session.add(
        CrewAvailability(
            crew_member_id=person.id,
            start_at=phase.start_at.date(),
            end_at=phase.end_at.date(),
            status=CrewAvailabilityStatus.LEAVE,
        )
    )
    session.commit()

    with pytest.raises(CrewHardConflictError, match="leave"):
        CrewPlanningService(session).assign(assignment_payload(phase, person, team))


def test_placeholder_headcount_and_daily_totals(session: Session) -> None:
    _, phase, _, team = seeded_phase_and_person(session)
    phase.required_headcount = 2
    session.commit()
    service = CrewPlanningService(session)
    service.assign(
        {
            "job_phase_id": phase.id,
            "crew_member_id": None,
            "placeholder_name": "Local crew 1",
            "tentmaster_id": team.id,
            "start_at": phase.start_at,
            "end_at": phase.end_at,
            "role": "Local crew",
            "assignment_source": "manual",
            "locked": False,
        }
    )

    headcount = service.phase_headcount(phase)
    totals = service.daily_totals(phase.start_at.date(), phase.start_at.date(), "Europe/London")
    assert headcount.assigned == 1
    assert headcount.shortfall == 1
    assert totals[phase.start_at.date()] == 1


def test_job_can_use_multiple_tentmasters_across_phases(session: Session) -> None:
    job, _, _, _ = seeded_phase_and_person(session)
    teams = session.scalars(select(Tentmaster).order_by(Tentmaster.id)).all()
    build = next(item for item in job.phases if item.phase_type == PhaseType.BUILD)
    strike = next(item for item in job.phases if item.phase_type == PhaseType.STRIKE)
    build.tentmaster_id = teams[0].id
    strike.tentmaster_id = teams[1].id
    session.commit()

    assert {build.tentmaster_id, strike.tentmaster_id} == {teams[0].id, teams[1].id}
