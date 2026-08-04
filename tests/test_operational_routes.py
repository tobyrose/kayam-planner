from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.crew_movements import CrewMovement
from app.models.jobs import Job
from app.models.logistics import Load


def test_operational_pages_render_with_showcase_data(session: Session, client: TestClient) -> None:
    seed_development_data(session, include_operational_demo=True)
    load = session.scalar(select(Load))
    crew_move = session.scalar(select(CrewMovement))
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    assert load is not None and crew_move is not None and job is not None
    paths = (
        "/planning?start=2026-06-01&end=2026-08-31",
        "/planning/flow?start=2026-06-01&end=2026-08-31",
        "/planning/roster?start=2026-06-01&days=92",
        f"/jobs/{job.id}",
        f"/jobs/{job.id}/summary",
        f"/jobs/{job.id}/edit",
        "/conflicts",
        "/loads",
        f"/loads/{load.id}",
        "/routes",
        "/crew-moves",
        f"/crew-moves/{crew_move.id}",
        "/costs",
        "/system",
        "/system/export.json",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path


def test_board_flow_and_roster_default_to_current_calendar_year(client: TestClient) -> None:
    year = date.today().year

    board = client.get("/planning")
    assert board.status_code == 200
    assert f'data-board-start="{year}-01-01"' in board.text
    assert f'data-board-end="{year}-12-31"' in board.text

    flow = client.get("/planning/flow")
    assert flow.status_code == 200
    assert f'value="{year}-01-01"' in flow.text
    assert f'value="{year}-12-31"' in flow.text

    roster = client.get("/planning/roster")
    assert roster.status_code == 200
    assert f'value="{year}-01-01"' in roster.text


def test_board_flow_and_roster_accept_explicit_year_selector(client: TestClient) -> None:
    target_year = date.today().year + 1

    board = client.get(f"/planning?year={target_year}")
    assert f'data-board-start="{target_year}-01-01"' in board.text
    assert f'data-board-end="{target_year}-12-31"' in board.text

    roster = client.get(f"/planning/roster?year={target_year}")
    assert f'value="{target_year}-01-01"' in roster.text


def test_board_flow_and_roster_explicit_range_wins_over_year_default(
    client: TestClient,
) -> None:
    board = client.get("/planning?start=2026-06-01&end=2026-06-30")
    assert 'data-board-start="2026-06-01"' in board.text
    assert 'data-board-end="2026-06-30"' in board.text

    roster = client.get("/planning/roster?start=2026-06-01&days=31")
    assert 'value="2026-06-01"' in roster.text


def test_job_page_splits_into_read_view_and_edit_surface(
    session: Session, client: TestClient
) -> None:
    seed_development_data(session, include_operational_demo=True)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    assert job is not None

    read_page = client.get(f"/jobs/{job.id}")
    assert read_page.status_code == 200
    assert f'action="/jobs/{job.id}/tent-requirements"' not in read_page.text
    assert f'action="/jobs/{job.id}/phases/new"' not in read_page.text
    assert f'action="/jobs/{job.id}/local-crew"' not in read_page.text
    assert job.name in read_page.text

    edit_page = client.get(f"/jobs/{job.id}/edit")
    assert edit_page.status_code == 200
    assert f'action="/jobs/{job.id}/tent-requirements"' in edit_page.text
    assert f'action="/jobs/{job.id}/phases/new"' in edit_page.text
    assert f'action="/jobs/{job.id}/phases/save-all"' in edit_page.text
    assert f'action="/jobs/{job.id}/local-crew"' in edit_page.text
    assert "Save all phases" in edit_page.text

    summary = client.get(f"/jobs/{job.id}/summary")
    assert summary.status_code == 200
    assert job.name in summary.text
    assert "<nav" not in summary.text
    assert f'action="/jobs/{job.id}/tent-requirements"' not in summary.text
    assert "Loads" in summary.text


def test_job_summary_lists_inbound_and_outbound_loads(
    session: Session, client: TestClient
) -> None:
    from datetime import UTC, datetime, timedelta

    from app.models.administration import EquipmentType, Location, LocationType, LorryType
    from app.models.jobs import CommercialStatus, Job
    from app.models.logistics import EquipmentMovement, Load, LoadItem, MovementStatus
    from app.services.jobs import JobService

    seed_development_data(session)
    yard = session.scalar(select(Location).where(Location.location_type == LocationType.YARD))
    site = Location(name="Panel Loads Site", location_type=LocationType.SITE)
    session.add(site)
    session.flush()
    lorry = session.scalar(select(LorryType).where(LorryType.active.is_(True)))
    equipment_type = session.scalar(select(EquipmentType).where(EquipmentType.code == "K"))
    assert yard is not None and lorry is not None and equipment_type is not None

    job = Job(
        job_code="PANEL-LOADS",
        name="Panel loads job",
        customer_name="Fixture",
        location_id=site.id,
        commercial_status=CommercialStatus.QUOTED,
    )
    session.add(job)
    session.commit()
    up = datetime(2026, 8, 20, 12, tzinfo=UTC)
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K",
            "quantity": 1,
            "contracted_up_at": up,
            "contracted_down_at": up + timedelta(days=4),
        },
    )
    inbound = EquipmentMovement(
        movement_code="PANEL-IN",
        origin_location_id=yard.id,
        destination_location_id=site.id,
        depart_after=up - timedelta(days=4),
        arrive_by=up - timedelta(days=3),
        status=MovementStatus.PLANNED,
    )
    inbound.loads.append(
        Load(
            load_number=41,
            lorry_type_id=lorry.id,
            items=[LoadItem(equipment_type_id=equipment_type.id, quantity=1)],
        )
    )
    outbound = EquipmentMovement(
        movement_code="PANEL-OUT",
        origin_location_id=site.id,
        destination_location_id=yard.id,
        depart_after=up + timedelta(days=4),
        arrive_by=up + timedelta(days=5),
        status=MovementStatus.PLANNED,
    )
    outbound.loads.append(
        Load(
            load_number=42,
            lorry_type_id=lorry.id,
            items=[LoadItem(equipment_type_id=equipment_type.id, quantity=1)],
        )
    )
    session.add_all([inbound, outbound])
    session.commit()

    summary = client.get(f"/jobs/{job.id}/summary")
    assert summary.status_code == 200
    assert "L41" in summary.text
    assert "L42" in summary.text
    assert "Arriving" in summary.text
    assert "Leaving" in summary.text
    assert equipment_type.code in summary.text


def test_roster_move_route_updates_membership_and_redirects(
    session: Session, client: TestClient
) -> None:
    from app.models.administration import CrewMember, Tentmaster, TentmasterMembership

    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    to_team = session.scalar(select(Tentmaster).where(Tentmaster.name == "Ross"))
    assert person is not None and to_team is not None

    response = client.post(
        "/planning/roster/move",
        data={
            "board_start": "2026-06-01",
            "crew_member_id": str(person.id),
            "to_tentmaster_id": str(to_team.id),
            "effective_date": "2026-06-15",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/planning/roster?start=2026-06-01")
    new_membership = session.scalar(
        select(TentmasterMembership).where(
            TentmasterMembership.crew_member_id == person.id,
            TentmasterMembership.tentmaster_id == to_team.id,
        )
    )
    assert new_membership is not None and new_membership.start_at.isoformat() == "2026-06-15"


def test_roster_move_route_unassigns_with_empty_tentmaster(
    session: Session, client: TestClient
) -> None:
    from app.models.administration import CrewMember, TentmasterMembership

    seed_development_data(session)
    person = session.scalar(select(CrewMember).where(CrewMember.name == "Demo Crew 1"))
    assert person is not None

    response = client.post(
        "/planning/roster/move",
        data={
            "board_start": "2026-06-01",
            "crew_member_id": str(person.id),
            "to_tentmaster_id": "",
            "effective_date": "2026-06-15",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    membership = session.scalar(
        select(TentmasterMembership).where(TentmasterMembership.crew_member_id == person.id)
    )
    assert membership is not None and membership.end_at.isoformat() == "2026-06-15"
