from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import EquipmentAsset, EquipmentType, Location, Tentmaster
from app.models.jobs import CommercialStatus, Job, JobPhase, PhaseType
from app.models.logistics import EquipmentMovement
from app.services.board import BoardService
from app.services.conflicts import ConflictCentreService
from app.services.jobs import JobService


def test_combined_board_and_json_endpoint(session: Session, client) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session)
    board = BoardService(session).build(date(2026, 6, 1), date(2026, 7, 31))
    assert len(board.days) == 61
    assert any(
        block.detail_lines
        for day in board.days
        for blocks in list(day.tentmasters.values()) + list(day.unassigned.values())
        for block in blocks
    )
    response = client.get("/api/planning/board?start=2026-06-01&end=2026-07-31")
    assert response.status_code == 200
    assert len(response.json()["days"]) == 61


def test_board_uses_bounded_queries(session: Session, test_engine) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session)
    location = session.scalar(select(Location))
    equipment_type = session.scalar(select(EquipmentType))
    assert location is not None and equipment_type is not None
    season_start = datetime(2026, 5, 1, 8, tzinfo=UTC)
    for index in range(300):
        session.add(
            EquipmentAsset(
                asset_code=f"PERF-{index:03}",
                equipment_type_id=equipment_type.id,
                initial_location_id=location.id,
            )
        )
        job = Job(
            job_code=f"PERF-JOB-{index:03}",
            name=f"Performance job {index}",
            customer_name="Performance fixture",
            location_id=location.id,
            site_access_at=season_start,
        )
        job.phases.append(
            JobPhase(
                phase_type=PhaseType.BUILD,
                start_at=season_start,
                end_at=season_start + timedelta(hours=8),
                required_headcount=0,
            )
        )
        session.add(job)
    session.commit()
    statements = 0

    def count_queries(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal statements
        statements += 1

    event.listen(test_engine, "before_cursor_execute", count_queries)
    try:
        BoardService(session).build(date(2026, 4, 1), date(2026, 9, 30))
    finally:
        event.remove(test_engine, "before_cursor_execute", count_queries)
    assert statements <= 20


def test_tentmaster_double_booking_is_flagged_as_conflict(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location))
    team = session.scalar(select(Tentmaster))
    assert location is not None and team is not None
    start = datetime(2026, 5, 1, 8, tzinfo=UTC)
    confirmed_job = Job(
        job_code="DOUBLE-BOOK-1",
        name="Double book confirmed",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.CONFIRMED,
        site_access_at=start,
    )
    confirmed_job.phases.append(
        JobPhase(
            phase_type=PhaseType.BUILD,
            tentmaster_id=team.id,
            start_at=start,
            end_at=start + timedelta(hours=8),
            required_headcount=0,
        )
    )
    overlapping_job = Job(
        job_code="DOUBLE-BOOK-2",
        name="Double book overlapping",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.QUOTED,
        site_access_at=start,
    )
    overlapping_job.phases.append(
        JobPhase(
            phase_type=PhaseType.BUILD,
            tentmaster_id=team.id,
            start_at=start + timedelta(hours=4),
            end_at=start + timedelta(hours=12),
            required_headcount=0,
        )
    )
    session.add_all([confirmed_job, overlapping_job])
    session.commit()

    conflicts = ConflictCentreService(session).conflicts()

    matches = [item for item in conflicts if item.category == "tentmaster"]
    assert matches and matches[0].severity == "hard"


def test_unassigned_phase_appears_only_in_unassigned_lane(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location))
    assert location is not None
    start = datetime(2026, 5, 1, 8, tzinfo=UTC)
    job = Job(
        job_code="NO-TM-1",
        name="Unassigned phase job",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.QUOTED,
        site_access_at=start,
    )
    job.phases.append(
        JobPhase(
            phase_type=PhaseType.BUILD,
            start_at=start,
            end_at=start + timedelta(hours=8),
            required_headcount=0,
        )
    )
    session.add(job)
    session.commit()

    board = BoardService(session).build(date(2026, 5, 1), date(2026, 5, 1))
    day = board.days[0]
    assert any(
        block.job_id == job.id for blocks in day.unassigned.values() for block in blocks
    )
    assert not any(
        block.job_id == job.id for blocks in day.tentmasters.values() for block in blocks
    )


def test_multi_day_phase_renders_as_one_contiguous_segment_run(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location))
    team = session.scalar(select(Tentmaster))
    assert location is not None and team is not None
    start = datetime(2026, 5, 1, tzinfo=UTC)
    job = Job(
        job_code="MULTI-DAY-1",
        name="Multi-day phase job",
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
            end_at=start + timedelta(days=3),
            required_headcount=0,
        )
    )
    session.add(job)
    session.commit()

    board = BoardService(session).build(date(2026, 5, 1), date(2026, 5, 3))
    segments = [
        next(block.segment for block in day.tentmasters[team.id] if block.job_id == job.id)
        for day in board.days
    ]
    assert segments == ["start", "mid", "end"]


def test_job_block_shows_tent_sequence_and_boundary_times(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location))
    team = session.scalar(select(Tentmaster))
    assert location is not None and team is not None
    start = datetime(2026, 5, 1, tzinfo=UTC)
    job = Job(
        job_code="DETAIL-1",
        name="Detail job",
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
            end_at=start + timedelta(days=3),
            required_headcount=0,
        )
    )
    session.add(job)
    session.commit()
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": start,
            "contracted_down_at": start + timedelta(days=3),
        },
    )

    board = BoardService(session).build(date(2026, 5, 1), date(2026, 5, 3))
    first = next(block for block in board.days[0].tentmasters[team.id] if block.job_id == job.id)
    last = next(block for block in board.days[2].tentmasters[team.id] if block.job_id == job.id)
    assert "KMMMK" in first.subtitle
    assert any("UP 00:00" in line for line in first.detail_lines)
    assert not any("BREAK" in line for line in first.detail_lines)
    assert any("BREAK 00:00" in line for line in last.detail_lines)


def test_up_card_hides_build_card_same_column_on_handover_day(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location))
    team = session.scalar(select(Tentmaster))
    assert location is not None and team is not None
    start = datetime(2026, 5, 1, tzinfo=UTC)
    job = Job(
        job_code="HANDOVER-1",
        name="Handover job",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.CONFIRMED,
        site_access_at=start,
    )
    job.phases.append(
        JobPhase(
            phase_type=PhaseType.BUILD,
            tentmaster_id=team.id,
            start_at=start - timedelta(days=2),
            end_at=start,
            required_headcount=0,
        )
    )
    session.add(job)
    session.commit()
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": start,
            "contracted_down_at": start + timedelta(days=3),
        },
    )
    up_phase = next(phase for phase in job.phases if phase.phase_type == PhaseType.UP)
    up_phase.tentmaster_id = team.id
    session.commit()

    board = BoardService(session).build(date(2026, 4, 29), date(2026, 5, 1))
    handover_day = board.days[-1]
    job_blocks = [
        block for block in handover_day.tentmasters[team.id] if block.job_id == job.id
    ]
    # Build ends and Up starts on the same day, same Tentmaster's column — only Up's card shows.
    assert len(job_blocks) == 1
    assert "up" in job_blocks[0].label


def test_build_card_still_shows_when_up_is_on_a_different_column(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(select(Location))
    teams = session.scalars(select(Tentmaster)).all()
    assert location is not None and len(teams) >= 2
    build_team, up_team = teams[0], teams[1]
    start = datetime(2026, 5, 1, tzinfo=UTC)
    job = Job(
        job_code="HANDOVER-2",
        name="Cross-team handover job",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.CONFIRMED,
        site_access_at=start,
    )
    job.phases.append(
        JobPhase(
            phase_type=PhaseType.BUILD,
            tentmaster_id=build_team.id,
            start_at=start - timedelta(days=2),
            end_at=start,
            required_headcount=0,
        )
    )
    session.add(job)
    session.commit()
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": start,
            "contracted_down_at": start + timedelta(days=3),
        },
    )
    up_phase = next(phase for phase in job.phases if phase.phase_type == PhaseType.UP)
    up_phase.tentmaster_id = up_team.id
    session.commit()

    board = BoardService(session).build(date(2026, 4, 29), date(2026, 5, 1))
    handover_day = board.days[-1]
    # Build is on its own Tentmaster's column, separate from Up's — it still needs its own card.
    assert any(
        block.job_id == job.id for block in handover_day.tentmasters[build_team.id]
    )
    assert any(block.job_id == job.id for block in handover_day.tentmasters[up_team.id])


def test_move_phase_route_reassigns_and_redirects(session: Session, client) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session)
    location = session.scalar(select(Location))
    teams = session.scalars(select(Tentmaster)).all()
    assert location is not None and len(teams) >= 2
    start = datetime(2026, 5, 1, 8, tzinfo=UTC)
    job = Job(
        job_code="MOVE-1",
        name="Move job",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.CONFIRMED,
        site_access_at=start,
    )
    job.phases.append(
        JobPhase(
            phase_type=PhaseType.BUILD,
            tentmaster_id=teams[0].id,
            start_at=start,
            end_at=start + timedelta(hours=8),
            required_headcount=0,
        )
    )
    session.add(job)
    session.commit()
    phase = job.phases[0]

    response = client.post(
        "/planning/move-phase",
        data={
            "board_start": "2026-05-01",
            "board_end": "2026-05-01",
            "phase_id": str(phase.id),
            "to_tentmaster_id": str(teams[1].id),
        },
    )
    assert response.status_code == 200  # TestClient follows the redirect
    session.refresh(phase)
    assert phase.tentmaster_id == teams[1].id


def test_conflict_centre_reports_and_suggestions_do_not_mutate(session: Session) -> None:
    seed_development_data(session)
    service = ConflictCentreService(session)
    before = session.scalar(select(func.count()).select_from(EquipmentMovement))
    conflicts = service.conflicts()
    service.direct_movement_suggestions()
    service.spare_load_suggestions()
    after = session.scalar(select(func.count()).select_from(EquipmentMovement))
    assert any(item.category == "equipment requirement" for item in conflicts)
    assert before == after
