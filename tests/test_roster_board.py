from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import (
    CrewAvailabilityWindow,
    CrewMember,
    Location,
    Tentmaster,
    TentmasterMembership,
)
from app.models.crew_planning import CrewActivity, CrewActivityType
from app.models.jobs import CommercialStatus, Job, JobPhase, PhaseType
from app.services.roster_board import RosterBoardError, RosterBoardService, RosterDay


def _entry(day: RosterDay, team_id: int, person: CrewMember):  # type: ignore[no-untyped-def]
    return next(
        (entry for entry in day.members_by_tentmaster[team_id] if entry.member.id == person.id),
        None,
    )


def test_roster_board_renders_members_and_unassigned(session: Session) -> None:
    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert person is not None and team is not None

    board = RosterBoardService(session).build(date(2026, 6, 1), date(2026, 6, 1))

    day = board.days[0]
    entry = _entry(day, team.id, person)
    assert entry is not None and entry.available
    assert person not in day.unassigned


def test_roster_board_shows_job_label_for_booked_tentmaster(session: Session) -> None:
    seed_development_data(session)
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    other_team = session.scalar(select(Tentmaster).where(Tentmaster.name != "Max/Martin"))
    location = session.scalar(select(Location))
    assert team is not None and other_team is not None and location is not None
    start = datetime(2026, 5, 1, tzinfo=UTC)
    job = Job(
        job_code="ROSTER-DETAIL-1",
        name="Roster detail job",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.CONFIRMED,
        site_access_at=start,
    )
    job.phases.append(
        JobPhase(
            phase_type=PhaseType.BUILD,
            tentmaster_id=team.id,
            start_at=start,
            end_at=start + timedelta(days=2),
            required_headcount=0,
        )
    )
    session.add(job)
    session.commit()

    board = RosterBoardService(session).build(date(2026, 5, 1), date(2026, 5, 1))
    day = board.days[0]
    assert day.shading_by_tentmaster[team.id] == "ROSTER-DETAIL-1"
    assert day.shading_by_tentmaster[other_team.id] == ""


def test_roster_board_shows_activity_label_for_booked_tentmaster(session: Session) -> None:
    seed_development_data(session)
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    other_team = session.scalar(select(Tentmaster).where(Tentmaster.name != "Max/Martin"))
    assert team is not None and other_team is not None
    start = datetime(2026, 5, 1, tzinfo=UTC)
    session.add(
        CrewActivity(
            activity_type=CrewActivityType.YARD_WORK,
            tentmaster_id=team.id,
            start_at=start,
            end_at=start + timedelta(days=1),
            title="Yard maintenance",
        )
    )
    session.commit()

    board = RosterBoardService(session).build(date(2026, 5, 1), date(2026, 5, 1))
    day = board.days[0]
    assert day.shading_by_tentmaster[team.id] == "Yard maintenance"
    assert day.shading_by_tentmaster[other_team.id] == ""


def test_move_crew_member_ends_old_membership_and_starts_new(session: Session) -> None:
    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    from_team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    to_team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Ross"))
    assert person is not None and from_team is not None and to_team is not None

    RosterBoardService(session).move_crew_member(person.id, to_team.id, date(2026, 6, 15))

    memberships = session.scalars(
        select(TentmasterMembership)
        .where(TentmasterMembership.crew_member_id == person.id)
        .order_by(TentmasterMembership.start_at)
    ).all()
    assert len(memberships) == 2
    assert memberships[0].tentmaster_id == from_team.id
    assert memberships[0].end_at == date(2026, 6, 15)
    assert memberships[1].tentmaster_id == to_team.id
    assert memberships[1].start_at == date(2026, 6, 15)
    assert memberships[1].end_at is None

    board = RosterBoardService(session).build(date(2026, 6, 14), date(2026, 6, 15))
    assert _entry(board.days[0], from_team.id, person) is not None
    assert _entry(board.days[1], to_team.id, person) is not None


def test_move_crew_member_rejects_move_to_current_team(session: Session) -> None:
    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert person is not None and team is not None

    with pytest.raises(RosterBoardError, match="already"):
        RosterBoardService(session).move_crew_member(person.id, team.id, date(2026, 6, 15))


def test_move_crew_member_to_unassigned_ends_membership_without_starting_new(
    session: Session,
) -> None:
    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert person is not None and team is not None

    RosterBoardService(session).move_crew_member(person.id, None, date(2026, 6, 15))

    memberships = session.scalars(
        select(TentmasterMembership).where(TentmasterMembership.crew_member_id == person.id)
    ).all()
    assert len(memberships) == 1
    assert memberships[0].end_at == date(2026, 6, 15)
    board = RosterBoardService(session).build(date(2026, 6, 15), date(2026, 6, 15))
    assert _entry(board.days[0], team.id, person) is None
    assert person in board.days[0].unassigned


def test_move_crew_member_to_unassigned_twice_raises(session: Session) -> None:
    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    assert person is not None

    RosterBoardService(session).move_crew_member(person.id, None, date(2026, 6, 15))

    with pytest.raises(RosterBoardError, match="already unassigned"):
        RosterBoardService(session).move_crew_member(person.id, None, date(2026, 6, 20))


def test_move_crew_member_slots_in_before_existing_future_membership(session: Session) -> None:
    """The exact scenario reported as broken: a person already scheduled onto a Tentmaster in
    the future should NOT block (or get overwritten by) an earlier move onto someone else —
    the earlier move should end exactly where the future one already begins, and the future one
    resumes untouched."""
    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    max_team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    marley = session.scalar(select(Tentmaster).where(Tentmaster.name == "Marley"))
    assert person is not None and max_team is not None and marley is not None

    session.execute(
        delete(TentmasterMembership).where(TentmasterMembership.crew_member_id == person.id)
    )
    session.add(
        TentmasterMembership(
            tentmaster_id=max_team.id,
            crew_member_id=person.id,
            start_at=date(2026, 8, 15),
            end_at=None,
        )
    )
    session.commit()

    # Previously this raised RosterBoardError("...conflicts with an existing Tentmaster
    # membership") even though 4 June is well before the 15 August segment.
    RosterBoardService(session).move_crew_member(person.id, marley.id, date(2026, 6, 4))

    memberships = session.scalars(
        select(TentmasterMembership)
        .where(TentmasterMembership.crew_member_id == person.id)
        .order_by(TentmasterMembership.start_at)
    ).all()
    assert len(memberships) == 2
    assert memberships[0].tentmaster_id == marley.id
    assert memberships[0].start_at == date(2026, 6, 4)
    assert memberships[0].end_at == date(2026, 8, 15)
    assert memberships[1].tentmaster_id == max_team.id
    assert memberships[1].start_at == date(2026, 8, 15)
    assert memberships[1].end_at is None

    board = RosterBoardService(session).build(date(2026, 6, 4), date(2026, 8, 15))
    assert _entry(board.days[0], marley.id, person) is not None
    assert _entry(board.days[-1], max_team.id, person) is not None


def test_move_crew_member_to_unassigned_clears_future_memberships(session: Session) -> None:
    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    max_team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    marley = session.scalar(select(Tentmaster).where(Tentmaster.name == "Marley"))
    assert person is not None and max_team is not None and marley is not None

    service = RosterBoardService(session)
    service.move_crew_member(person.id, marley.id, date(2026, 6, 4))
    service.move_crew_member(person.id, max_team.id, date(2026, 8, 15))

    # Unassigning mid-Marley should clear the already-scheduled future Max segment too —
    # "unassigned for the rest of time" has no resume point, unlike a Tentmaster-to-Tentmaster move.
    service.move_crew_member(person.id, None, date(2026, 7, 1))

    memberships = session.scalars(
        select(TentmasterMembership)
        .where(TentmasterMembership.crew_member_id == person.id)
        .order_by(TentmasterMembership.start_at)
    ).all()
    assert all(row.start_at <= date(2026, 7, 1) for row in memberships)
    assert memberships[-1].tentmaster_id == marley.id
    assert memberships[-1].end_at == date(2026, 7, 1)

    board = RosterBoardService(session).build(date(2026, 8, 15), date(2026, 8, 15))
    assert _entry(board.days[0], max_team.id, person) is None
    assert person in board.days[0].unassigned


def test_move_crew_member_same_day_second_move_replaces_todays_membership(
    session: Session,
) -> None:
    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    ross = session.scalar(select(Tentmaster).where(Tentmaster.name == "Ross"))
    jesse = session.scalar(select(Tentmaster).where(Tentmaster.name == "Jesse"))
    assert person is not None and ross is not None and jesse is not None
    move_date = date(2026, 6, 15)

    service = RosterBoardService(session)
    service.move_crew_member(person.id, ross.id, move_date)
    service.move_crew_member(person.id, jesse.id, move_date)

    memberships = session.scalars(
        select(TentmasterMembership).where(
            TentmasterMembership.crew_member_id == person.id,
            TentmasterMembership.start_at == move_date,
        )
    ).all()
    assert len(memberships) == 1
    assert memberships[0].tentmaster_id == jesse.id


def test_roster_board_greys_out_member_outside_availability_window(session: Session) -> None:
    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert person is not None and team is not None
    session.add(
        CrewAvailabilityWindow(
            crew_member_id=person.id, start_at=date(2026, 5, 25), end_at=date(2026, 6, 17)
        )
    )
    session.commit()

    board = RosterBoardService(session).build(date(2026, 6, 1), date(2026, 6, 20))

    in_window_day = board.days[0]  # 2026-06-01
    out_of_window_day = board.days[-1]  # 2026-06-20
    in_window_entry = _entry(in_window_day, team.id, person)
    out_of_window_entry = _entry(out_of_window_day, team.id, person)
    assert in_window_entry is not None and in_window_entry.available
    # Still shown against their Tentmaster (greyed), not hidden entirely, and not counted as
    # unassigned either — they're still assigned, just unavailable that day.
    assert out_of_window_entry is not None and not out_of_window_entry.available
    assert person not in out_of_window_day.unassigned


def test_roster_board_shows_member_with_no_windows_as_always_available(session: Session) -> None:
    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Max/Martin"))
    assert person is not None and team is not None

    board = RosterBoardService(session).build(date(2020, 1, 1), date(2020, 1, 1))

    # Far outside any seeded membership window too, but with zero CrewAvailabilityWindow rows
    # the person should simply follow membership rules (absent here because membership starts
    # 2026-01-01), not be excluded specifically by the availability-window check.
    assert _entry(board.days[0], team.id, person) is None
    assert person in board.days[0].unassigned
