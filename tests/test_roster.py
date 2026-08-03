from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import (
    CrewAvailability,
    CrewAvailabilityStatus,
    CrewAvailabilityWindow,
    Tentmaster,
)
from app.models.jobs import Job, PhaseType
from app.services.roster import RosterIndex, roster_for_tentmaster


def test_roster_for_tentmaster_returns_active_members(session: Session) -> None:
    seed_development_data(session)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert job is not None and team is not None
    phase = next(item for item in job.phases if item.phase_type == PhaseType.BUILD)

    members = roster_for_tentmaster(session, team.id, phase.start_at, phase.end_at)

    assert [member.name for member in members] == ["Demo Crew 1"]


def test_roster_for_unknown_tentmaster_is_empty(session: Session) -> None:
    seed_development_data(session)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    assert job is not None
    phase = next(item for item in job.phases if item.phase_type == PhaseType.BUILD)

    assert roster_for_tentmaster(session, 999999, phase.start_at, phase.end_at) == []
    index = RosterIndex.build(session, phase.start_at, phase.end_at)
    assert index.roster_for(None, phase.start_at, phase.end_at) == []


def test_roster_excludes_member_on_leave(session: Session) -> None:
    seed_development_data(session)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert job is not None and team is not None
    phase = next(item for item in job.phases if item.phase_type == PhaseType.BUILD)
    member = next(m for m in roster_for_tentmaster(session, team.id, phase.start_at, phase.end_at))
    session.add(
        CrewAvailability(
            crew_member_id=member.id,
            start_at=phase.start_at.date(),
            end_at=phase.end_at.date(),
            status=CrewAvailabilityStatus.LEAVE,
        )
    )
    session.commit()

    assert roster_for_tentmaster(session, team.id, phase.start_at, phase.end_at) == []


def test_roster_respects_default_available_override_status(session: Session) -> None:
    seed_development_data(session)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert job is not None and team is not None
    phase = next(item for item in job.phases if item.phase_type == PhaseType.BUILD)
    member = next(m for m in roster_for_tentmaster(session, team.id, phase.start_at, phase.end_at))
    session.add(
        CrewAvailability(
            crew_member_id=member.id,
            start_at=phase.start_at.date(),
            end_at=phase.end_at.date(),
            status=CrewAvailabilityStatus.AVAILABLE_OVERRIDE,
        )
    )
    session.commit()

    members = roster_for_tentmaster(session, team.id, phase.start_at, phase.end_at)
    assert [m.name for m in members] == ["Demo Crew 1"]


def test_roster_excludes_member_with_no_matching_availability_window(session: Session) -> None:
    seed_development_data(session)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert job is not None and team is not None
    phase = next(item for item in job.phases if item.phase_type == PhaseType.BUILD)
    member = next(m for m in roster_for_tentmaster(session, team.id, phase.start_at, phase.end_at))
    session.add(
        CrewAvailabilityWindow(
            crew_member_id=member.id,
            start_at=phase.end_at.date() + timedelta(days=30),
            end_at=phase.end_at.date() + timedelta(days=60),
        )
    )
    session.commit()

    assert roster_for_tentmaster(session, team.id, phase.start_at, phase.end_at) == []


def test_roster_includes_member_with_matching_availability_window(session: Session) -> None:
    seed_development_data(session)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert job is not None and team is not None
    phase = next(item for item in job.phases if item.phase_type == PhaseType.BUILD)
    member = next(m for m in roster_for_tentmaster(session, team.id, phase.start_at, phase.end_at))
    session.add_all(
        [
            CrewAvailabilityWindow(
                crew_member_id=member.id,
                start_at=phase.start_at.date() - timedelta(days=5),
                end_at=phase.end_at.date() + timedelta(days=5),
            ),
            CrewAvailabilityWindow(
                crew_member_id=member.id,
                start_at=phase.end_at.date() + timedelta(days=30),
                end_at=None,
            ),
        ]
    )
    session.commit()

    members = roster_for_tentmaster(session, team.id, phase.start_at, phase.end_at)
    assert [m.name for m in members] == ["Demo Crew 1"]


def test_roster_excludes_membership_outside_window(session: Session) -> None:
    seed_development_data(session)
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert team is not None
    far_past_start = datetime(2020, 1, 1, tzinfo=UTC)
    far_past_end = far_past_start + timedelta(days=1)

    assert roster_for_tentmaster(session, team.id, far_past_start, far_past_end) == []


def test_roster_index_build_is_bounded_query_count(session: Session, test_engine) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session)
    statements = 0

    def count_queries(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal statements
        statements += 1

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=370)
    event.listen(test_engine, "before_cursor_execute", count_queries)
    try:
        index = RosterIndex.build(session, start, end)
        teams = session.scalars(select(Tentmaster)).all()
        for team in teams:
            index.roster_for(team.id, start, end)
    finally:
        event.remove(test_engine, "before_cursor_execute", count_queries)
    # 3 queries for RosterIndex.build() itself (memberships, unavailable, windows), plus the
    # teams lookup used only for this test.
    assert statements <= 5
