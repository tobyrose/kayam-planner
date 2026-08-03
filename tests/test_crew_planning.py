from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import CrewMember, Tentmaster
from app.models.jobs import Job, JobPhase, PhaseType
from app.services.crew_planning import CrewPlanningService
from app.services.jobs import JobService


def seeded_phase_and_person(session: Session) -> tuple[Job, JobPhase, CrewMember, Tentmaster]:
    seed_development_data(session)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert job is not None and person is not None and team is not None
    phase = next(item for item in job.phases if item.phase_type == PhaseType.BUILD)
    return job, phase, person, team


def test_phase_headcount_derives_from_tentmaster_roster(session: Session) -> None:
    job, phase, person, team = seeded_phase_and_person(session)
    phase.tentmaster_id = team.id
    phase.required_headcount = 1
    session.commit()

    headcount = CrewPlanningService(session).phase_headcount(phase)
    assert person.name in headcount.names
    assert headcount.assigned == 1
    assert headcount.shortfall == 0


def test_local_crew_booking_adds_to_headcount_and_daily_totals(session: Session) -> None:
    job, phase, _, _ = seeded_phase_and_person(session)
    phase.required_headcount = 10
    session.commit()

    JobService(session).add_local_crew_booking(
        job.id,
        {
            "headcount": 4,
            "start_at": phase.start_at,
            "end_at": phase.end_at,
            "notes": "Test local crew",
        },
    )
    session.expire(job, ["local_crew_bookings"])
    session.refresh(phase)

    service = CrewPlanningService(session)
    headcount = service.phase_headcount(phase)
    totals = service.daily_totals(phase.start_at.date(), phase.start_at.date(), "Europe/London")
    assert headcount.assigned == 4
    assert headcount.shortfall == 6
    assert totals[phase.start_at.date()] == 4


def test_local_crew_booking_outside_phase_dates_does_not_count(session: Session) -> None:
    job, phase, _, _ = seeded_phase_and_person(session)
    session.commit()

    JobService(session).add_local_crew_booking(
        job.id,
        {
            "headcount": 3,
            "start_at": phase.end_at,
            "end_at": phase.end_at.replace(year=phase.end_at.year + 1),
            "notes": "Long after the build phase",
        },
    )
    session.expire(job, ["local_crew_bookings"])
    session.refresh(phase)

    headcount = CrewPlanningService(session).phase_headcount(phase)
    assert headcount.assigned == 0


def test_delete_local_crew_booking(session: Session) -> None:
    job, phase, _, _ = seeded_phase_and_person(session)
    session.commit()
    booking = JobService(session).add_local_crew_booking(
        job.id,
        {"headcount": 2, "start_at": phase.start_at, "end_at": phase.end_at, "notes": None},
    )

    JobService(session).delete_local_crew_booking(job.id, booking.id)
    session.expire(job, ["local_crew_bookings"])
    assert job.local_crew_bookings == []


def test_job_can_use_multiple_tentmasters_across_phases(session: Session) -> None:
    job, _, _, _ = seeded_phase_and_person(session)
    teams = session.scalars(select(Tentmaster).order_by(Tentmaster.id)).all()
    build = next(item for item in job.phases if item.phase_type == PhaseType.BUILD)
    brk = next(item for item in job.phases if item.phase_type == PhaseType.BREAK)
    build.tentmaster_id = teams[0].id
    brk.tentmaster_id = teams[1].id
    session.commit()

    assert {build.tentmaster_id, brk.tentmaster_id} == {teams[0].id, teams[1].id}
