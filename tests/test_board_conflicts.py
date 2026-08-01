from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import EquipmentAsset, EquipmentType, Location
from app.models.jobs import Job, JobPhase, PhaseType
from app.models.logistics import EquipmentMovement
from app.services.board import BoardService
from app.services.conflicts import ConflictCentreService


def test_combined_board_and_json_endpoint(session: Session, client) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session)
    board = BoardService(session).build(date(2026, 6, 1), date(2026, 7, 31))
    assert len(board.days) == 61
    assert any(day.operations for day in board.days)
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
            must_be_up_at=season_start + timedelta(hours=8),
            strike_available_at=season_start + timedelta(days=1),
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
