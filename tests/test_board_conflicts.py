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


def test_season_board_html_puts_unassigned_jobs_in_ua_cells(
    session: Session, client
) -> None:  # type: ignore[no-untyped-def]
    """Regression: unassigned work must not render under a Tentmaster column in the HTML."""
    seed_development_data(session)
    location = session.scalar(select(Location))
    assert location is not None
    start = datetime(2026, 6, 10, 8, tzinfo=UTC)
    job = Job(
        job_code="UA-HTML-1",
        name="Unassigned HTML placement",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.QUOTED,
        site_access_at=start,
    )
    job.phases.append(
        JobPhase(
            phase_type=PhaseType.BUILD,
            start_at=start,
            end_at=start + timedelta(days=2),
            required_headcount=0,
        )
    )
    session.add(job)
    session.commit()

    response = client.get("/planning?start=2026-06-10&end=2026-06-12")
    assert response.status_code == 200
    html = response.text
    assert 'data-ua-column=' in html
    assert 'class="ua-lane' in html or 'class="ua-lane ua-first"' in html
    # Job label appears; the block's parent cell must be an unassigned drop cell
    assert "UA-HTML-1" in html
    # Tentmaster cells carry a non-empty data-tentmaster-id; unassigned cells use empty string.
    # Ensure the job's phase-id block only sits in a data-tentmaster-id="" cell.
    import re

    for match in re.finditer(
        r'<td class="lane-cell phase-drop-cell[^"]*" data-tentmaster-id="([^"]*)"[^>]*>(.*?)</td>',
        html,
        re.DOTALL,
    ):
        tentmaster_id, cell_html = match.group(1), match.group(2)
        if "UA-HTML-1" in cell_html:
            assert tentmaster_id == "", (
                "Unassigned job block must live in a cell with empty data-tentmaster-id"
            )


def test_multi_day_block_labels_only_on_start_segment_in_html(
    session: Session, client
) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session)
    location = session.scalar(select(Location))
    team = session.scalar(select(Tentmaster))
    assert location is not None and team is not None
    start = datetime(2026, 5, 1, tzinfo=UTC)
    job = Job(
        job_code="SEG-HTML-1",
        name="Segment label job",
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

    response = client.get("/planning?start=2026-05-01&end=2026-05-03")
    html = response.text
    # Visible label element only on start/solo (mid/end use visually-hidden spans + title attrs)
    assert html.count('class="block-label"') == 1
    assert 'class="block-label">SEG-HTML-1 · build</strong>' in html
    assert 'data-segment="start"' in html
    assert 'data-segment="mid"' in html
    assert 'data-segment="end"' in html
    assert "phase-build" in html


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
    # Wall-clock contract times in the app default timezone (not bare midnight UTC, which
    # shifts calendar day when converted to Europe/London).
    from zoneinfo import ZoneInfo

    london = ZoneInfo("Europe/London")
    up_at = datetime(2026, 5, 1, 18, 0, tzinfo=london)
    down_at = datetime(2026, 5, 3, 13, 0, tzinfo=london)
    job = Job(
        job_code="DETAIL-1",
        name="Detail job",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.CONFIRMED,
        site_access_at=up_at,
    )
    session.add(job)
    session.commit()
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-M-K",
            "quantity": 1,
            "contracted_up_at": up_at,
            "contracted_down_at": down_at,
        },
    )
    session.refresh(job)
    for phase in job.phases:
        phase.tentmaster_id = team.id
    session.commit()

    board = BoardService(session).build(date(2026, 5, 1), date(2026, 5, 3))
    up_day = next(
        block
        for block in board.days[0].tentmasters[team.id]
        if block.job_id == job.id and block.phase_type == "up"
    )
    break_day = next(
        block
        for block in board.days[2].tentmasters[team.id]
        if block.job_id == job.id and block.phase_type == "break"
    )
    assert "KMMMK" in up_day.subtitle
    assert "up 18:00" in up_day.label
    assert any(line.startswith("UP 18:00") for line in up_day.detail_lines)
    assert "break 13:00" in break_day.label
    assert any(line.startswith("BREAK 13:00") for line in break_day.detail_lines)


def test_board_marks_conflict_when_sections_not_covered_by_loads(session: Session) -> None:
    """Red attention when required sections are not fully arriving on loads to the site."""
    seed_development_data(session)
    location = session.scalar(select(Location))
    team = session.scalar(select(Tentmaster))
    assert location is not None and team is not None
    from zoneinfo import ZoneInfo

    from app.models.administration import LorryType
    from app.models.logistics import EquipmentMovement, Load, LoadItem, MovementStatus
    from app.models.jobs import JobEquipmentRequirement, RequirementSource

    london = ZoneInfo("Europe/London")
    up_at = datetime(2026, 7, 10, 18, 0, tzinfo=london)
    down_at = datetime(2026, 7, 20, 18, 0, tzinfo=london)
    job = Job(
        job_code="SEC-COV-1",
        name="Section coverage job",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.QUOTED,
        site_access_at=up_at,
    )
    session.add(job)
    session.commit()
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-K",
            "quantity": 1,
            "contracted_up_at": up_at,
            "contracted_down_at": down_at,
        },
    )
    session.refresh(job)
    for phase in job.phases:
        phase.tentmaster_id = team.id
    session.commit()

    board = BoardService(session).build(date(2026, 7, 5), date(2026, 7, 12))
    build_blocks = [
        block
        for day in board.days
        for block in day.tentmasters[team.id]
        if block.job_id == job.id and block.phase_type == "build"
    ]
    assert build_blocks
    assert all(block.conflict for block in build_blocks)
    assert any(
        any(line.startswith("Kit short:") for line in block.detail_lines)
        for block in build_blocks
        if block.segment in ("start", "solo")
    )

    # Cover all required sections + poles with a load arriving in the job window.
    yard = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    lorry = session.scalar(select(LorryType).where(LorryType.active.is_(True)))
    assert yard is not None and lorry is not None
    movement = EquipmentMovement(
        movement_code="SEC-COV-MV",
        origin_location_id=yard.id,
        destination_location_id=location.id,
        depart_after=up_at - timedelta(days=4),
        arrive_by=up_at - timedelta(days=3),
        status=MovementStatus.REQUIRED,
    )
    session.add(movement)
    session.flush()
    load = Load(
        equipment_movement_id=movement.id,
        load_number=99,
        lorry_type_id=lorry.id,
    )
    session.add(load)
    session.flush()
    for requirement in job.equipment_requirements:
        if requirement.equipment_type.category not in {"section", "pole"}:
            continue
        session.add(
            LoadItem(
                load_id=load.id,
                equipment_type_id=requirement.equipment_type_id,
                quantity=requirement.quantity_required,
            )
        )
    session.commit()

    board_ok = BoardService(session).build(date(2026, 7, 5), date(2026, 7, 12))
    # Without crew roster, crew shortfall may still conflict — only assert section line is gone.
    start_build = next(
        block
        for day in board_ok.days
        for block in day.tentmasters[team.id]
        if block.job_id == job.id
        and block.phase_type == "build"
        and block.segment in ("start", "solo")
    )
    assert not any(line.startswith("Kit short:") for line in start_build.detail_lines)


def test_multi_tent_up_phases_merge_into_one_board_block(session: Session) -> None:
    """SOLIDAYS-style: two Up phases for one job in the same column → one block per day."""
    seed_development_data(session)
    location = session.scalar(select(Location))
    assert location is not None
    from zoneinfo import ZoneInfo

    london = ZoneInfo("Europe/London")
    job = Job(
        job_code="TWO-TENT",
        name="Two tent job",
        customer_name="Fixture",
        location_id=location.id,
        commercial_status=CommercialStatus.QUOTED,
        site_access_at=datetime(2026, 6, 17, 8, tzinfo=london),
    )
    session.add(job)
    session.commit()
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-K",
            "quantity": 1,
            "custom_name": "Tent A",
            "contracted_up_at": datetime(2026, 6, 17, 18, 0, tzinfo=london),
            "contracted_down_at": datetime(2026, 7, 1, 18, 0, tzinfo=london),
        },
    )
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "s-m-s",
            "quantity": 1,
            "custom_name": "Tent B",
            "contracted_up_at": datetime(2026, 6, 18, 17, 0, tzinfo=london),
            "contracted_down_at": datetime(2026, 7, 1, 13, 0, tzinfo=london),
        },
    )

    board = BoardService(session).build(date(2026, 6, 17), date(2026, 6, 20))
    for day in board.days:
        up_blocks = [
            block
            for blocks in day.unassigned.values()
            for block in blocks
            if block.job_id == job.id and block.phase_type == "up"
        ]
        assert len(up_blocks) == 1, f"{day.day}: expected one Up block, got {len(up_blocks)}"
    # First day: only first tent is up — still one block
    first_ups = [
        block
        for blocks in board.days[0].unassigned.values()
        for block in blocks
        if block.job_id == job.id and block.phase_type == "up"
    ]
    assert first_ups[0].segment == "start"
    # Diary: only Tent A's Up on the 17th — Tent B's 18th time must not appear early.
    assert "Tent A" in first_ups[0].label
    assert "Tent B" not in first_ups[0].label
    assert any("Tent A" in line for line in first_ups[0].detail_lines)
    assert not any("Tent B" in line for line in first_ups[0].detail_lines)
    # 18th: still one merged bar; only Tent B's contract Up shows that day.
    both_ups = [
        block
        for blocks in board.days[1].unassigned.values()
        for block in blocks
        if block.job_id == job.id and block.phase_type == "up"
    ]
    assert both_ups[0].segment == "mid"
    assert "Tent B" in both_ups[0].label
    assert "Tent A" not in both_ups[0].label
    assert "18:00" not in both_ups[0].label  # Tent A's time must not repeat on mid days
    assert any("Tent B" in line for line in both_ups[0].detail_lines)
    assert not any("Tent A" in line for line in both_ups[0].detail_lines)
    # Quiet mid day (19th): no contract clock in the label
    quiet = [
        block
        for blocks in board.days[2].unassigned.values()
        for block in blocks
        if block.job_id == job.id and block.phase_type == "up"
    ]
    assert quiet and "up" in quiet[0].label.lower()
    assert ":" not in quiet[0].label  # no HH:MM on non-contract days


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
