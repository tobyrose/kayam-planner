from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.commands.seed import seed_development_data
from app.models.administration import Location, LorryType, Tentmaster
from app.models.jobs import CommercialStatus, Job, PhaseType, RecordSource
from app.models.logistics import EquipmentMovement, Load, LoadItem
from app.models.crew_movements import CrewMovement
from app.services.jobs import JobService
from app.services.season_plan import SeasonPlanService, _pack_quantities

LONDON = ZoneInfo("Europe/London")


def test_pack_quantities_splits_over_flat_capacity() -> None:
    # Flat 7.2; K = 1.2 → 6 per lorry; 8 Ks → two loads
    packs = _pack_quantities(
        {"K": 8},
        {"K": Decimal("1.2")},
        Decimal("7.2"),
    )
    assert len(packs) == 2
    assert sum(pack["K"] for pack in packs) == 8


def test_generate_season_creates_loads_from_yard(session: Session) -> None:
    seed_development_data(session)
    location = session.scalar(
        select(Location).where(Location.name != "Oxford Yard")
    ) or session.scalar(select(Location))
    assert location is not None
    # Use a dedicated site if demo sites exist
    sites = session.scalars(select(Location)).all()
    site = next((loc for loc in sites if loc.name != "Oxford Yard"), location)

    job = Job(
        job_code="PLAN-JOB-1",
        name="Plan job",
        customer_name="Fixture",
        location_id=site.id,
        commercial_status=CommercialStatus.QUOTED,
    )
    session.add(job)
    session.commit()
    up = datetime(2026, 8, 10, 18, 0, tzinfo=LONDON)
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-M-K",
            "quantity": 1,
            "contracted_up_at": up,
            "contracted_down_at": up + timedelta(days=5),
        },
    )
    team = session.scalar(select(Tentmaster))
    assert team is not None
    session.refresh(job)
    for phase in job.phases:
        phase.tentmaster_id = team.id
    session.commit()

    result = SeasonPlanService(session).generate(include_crew_moves=False)
    assert result.loads_created >= 1
    assert result.movements_created >= 1
    loads = session.scalars(select(Load)).all()
    auto = [load for load in loads if load.notes and "AUTO-GENERATED" in load.notes]
    assert auto
    assert all(load.movement.source == RecordSource.GENERATED for load in auto)
    # Sections for K-M-M-K: K×2 M×2 should appear across load items
    totals: dict[str, int] = {}
    for load in auto:
        for item in load.items:
            code = item.resolved_type.code
            totals[code] = totals.get(code, 0) + item.quantity
    assert totals.get("K", 0) >= 2
    assert totals.get("M", 0) >= 2
    # King poles (derived) must also ship
    assert totals.get("P", 0) >= 1


def test_generate_season_respects_locked_loads(session: Session) -> None:
    seed_development_data(session)
    site = next(
        loc
        for loc in session.scalars(select(Location)).all()
        if loc.name != "Oxford Yard"
    )
    yard = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    lorry = session.scalar(select(LorryType).where(LorryType.active.is_(True)))
    assert yard is not None and lorry is not None

    job = Job(
        job_code="LOCK-JOB-1",
        name="Locked plan job",
        customer_name="Fixture",
        location_id=site.id,
        commercial_status=CommercialStatus.QUOTED,
    )
    session.add(job)
    session.commit()
    up = datetime(2026, 9, 1, 18, 0, tzinfo=LONDON)
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-K",
            "quantity": 1,
            "contracted_up_at": up,
            "contracted_down_at": up + timedelta(days=4),
        },
    )
    session.refresh(job)

    movement = EquipmentMovement(
        movement_code="LOCKED-MV",
        origin_location_id=yard.id,
        destination_location_id=site.id,
        depart_after=up - timedelta(days=3),
        arrive_by=up - timedelta(days=2),
        source=RecordSource.GENERATED,
        locked=True,
        notes="AUTO-GENERATED season plan — locked fixture",
    )
    session.add(movement)
    session.flush()
    load = Load(
        equipment_movement_id=movement.id,
        load_number=50,
        lorry_type_id=lorry.id,
        locked=True,
        notes="AUTO-GENERATED season plan — locked fixture",
    )
    session.add(load)
    session.commit()

    result = SeasonPlanService(session).generate(include_crew_moves=False)
    assert session.get(EquipmentMovement, movement.id) is not None
    assert session.get(Load, load.id) is not None
    assert result.auto_loads_removed == 0 or session.get(Load, load.id).locked


def test_generate_crew_moves_between_tentmaster_jobs(session: Session) -> None:
    seed_development_data(session)
    sites = [loc for loc in session.scalars(select(Location)).all() if loc.name != "Oxford Yard"]
    if len(sites) < 2:
        # Create second site
        second = Location(
            name="Season Plan Site B",
            location_type=sites[0].location_type,
            country_code="GB",
            timezone="Europe/London",
        )
        session.add(second)
        session.commit()
        sites.append(second)
    team = session.scalar(select(Tentmaster))
    assert team is not None

    for index, site in enumerate(sites[:2]):
        job = Job(
            job_code=f"CM-JOB-{index + 1}",
            name=f"Crew move job {index + 1}",
            customer_name="Fixture",
            location_id=site.id,
            commercial_status=CommercialStatus.QUOTED,
        )
        session.add(job)
        session.commit()
        up = datetime(2026, 7, 1 + index * 14, 18, 0, tzinfo=LONDON)
        JobService(session).add_tent_requirement(
            job.id,
            {
                "sequence": "K-M-K",
                "quantity": 1,
                "contracted_up_at": up,
                "contracted_down_at": up + timedelta(days=5),
            },
        )
        session.refresh(job)
        for phase in job.phases:
            phase.tentmaster_id = team.id
        session.commit()

    result = SeasonPlanService(session).generate(include_crew_moves=True)
    assert result.crew_moves_created >= 1
    moves = session.scalars(select(CrewMovement)).all()
    auto = [move for move in moves if move.notes and "AUTO-GENERATED" in move.notes]
    assert auto
    assert auto[0].tentmaster_id == team.id


def test_generate_season_route(session: Session, client) -> None:  # type: ignore[no-untyped-def]
    seed_development_data(session)
    response = client.post("/loads/generate-season", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/loads?plan=")


def test_generate_season_returns_kit_to_yard_after_last_job(session: Session) -> None:
    """Any stock left on site after the season must ship back to the Yard."""
    from app.models.administration import LocationType
    from app.services.section_coverage import loadable_requirements

    seed_development_data(session)
    yard = session.scalar(select(Location).where(Location.name == "Oxford Yard"))
    assert yard is not None
    # Dedicated site so other seed jobs do not share the free-pool location
    site = Location(
        name="Return Yard Site",
        location_type=LocationType.SITE,
        country_code="GB",
        timezone="Europe/London",
    )
    session.add(site)
    session.commit()
    team = session.scalar(select(Tentmaster))
    assert team is not None

    job = Job(
        job_code="RETURN-JOB-1",
        name="Return to yard job",
        customer_name="Fixture",
        location_id=site.id,
        commercial_status=CommercialStatus.QUOTED,
    )
    session.add(job)
    session.commit()
    up = datetime(2026, 9, 10, 18, 0, tzinfo=LONDON)
    down = up + timedelta(days=5)
    JobService(session).add_tent_requirement(
        job.id,
        {
            "sequence": "K-M-K",
            "quantity": 1,
            "contracted_up_at": up,
            "contracted_down_at": down,
        },
    )
    session.refresh(job)
    for phase in job.phases:
        phase.tentmaster_id = team.id
    session.commit()

    required = loadable_requirements(job)
    SeasonPlanService(session).generate(include_crew_moves=False)
    loads = session.scalars(
        select(Load).options(selectinload(Load.movement))
    ).all()
    auto = [
        load
        for load in loads
        if load.notes and "AUTO-GENERATED" in load.notes
    ]
    returns = [
        load
        for load in auto
        if load.movement.origin_location_id == site.id
        and load.movement.destination_location_id == yard.id
    ]
    # Inbound may be yard→site and/or job→job; either way the site must return kit after Down
    assert returns, "expected site → yard return loads"
    for load in returns:
        assert load.movement.depart_after >= down
        assert "YARD-RETURN" in (load.notes or "")
    in_totals: dict[str, int] = {}
    for load in returns:
        for item in load.items:
            code = item.resolved_type.code
            in_totals[code] = in_totals.get(code, 0) + int(item.quantity)
    for code, qty in required.items():
        assert in_totals.get(code, 0) >= qty, f"{code}: need {qty} return {in_totals.get(code, 0)}"


def test_job_to_job_leaves_at_donor_break_not_just_in_time(session: Session) -> None:
    """Donor kit must leave when free (contract Down), not sit until next build day."""
    seed_development_data(session)
    sites = [loc for loc in session.scalars(select(Location)).all() if loc.name != "Oxford Yard"]
    if len(sites) < 2:
        second = Location(
            name="Season Plan Site B",
            location_type=sites[0].location_type,
            country_code="GB",
            timezone="Europe/London",
        )
        session.add(second)
        session.commit()
        sites.append(second)
    site_a, site_b = sites[0], sites[1]
    team = session.scalar(select(Tentmaster))
    assert team is not None

    donor = Job(
        job_code="JJ-DONOR",
        name="Job-job donor",
        customer_name="Fixture",
        location_id=site_a.id,
        commercial_status=CommercialStatus.QUOTED,
    )
    receiver = Job(
        job_code="JJ-RECV",
        name="Job-job receiver",
        customer_name="Fixture",
        location_id=site_b.id,
        commercial_status=CommercialStatus.QUOTED,
    )
    session.add_all([donor, receiver])
    session.commit()

    down_a = datetime(2026, 7, 5, 17, 0, tzinfo=LONDON)
    up_a = down_a - timedelta(days=6)
    JobService(session).add_tent_requirement(
        donor.id,
        {
            "sequence": "K-M-K",
            "quantity": 1,
            "contracted_up_at": up_a,
            "contracted_down_at": down_a,
        },
    )
    # Receiver needs same kit ~3 weeks later
    up_b = datetime(2026, 7, 28, 17, 0, tzinfo=LONDON)
    JobService(session).add_tent_requirement(
        receiver.id,
        {
            "sequence": "K-M-K",
            "quantity": 1,
            "contracted_up_at": up_b,
            "contracted_down_at": up_b + timedelta(days=5),
        },
    )
    for job_id in (donor.id, receiver.id):
        job = session.get(Job, job_id)
        assert job is not None
        for phase in job.phases:
            phase.tentmaster_id = team.id
    session.commit()

    SeasonPlanService(session).generate(include_crew_moves=False)
    loads = session.scalars(
        select(Load).options(selectinload(Load.movement))
    ).all()
    job_job = [
        load
        for load in loads
        if load.notes
        and "AUTO-GENERATED" in load.notes
        and load.movement.origin_location_id == site_a.id
        and load.movement.destination_location_id == site_b.id
    ]
    assert job_job, "expected at least one job→job load from donor site"
    for load in job_job:
        # Must leave within a day of donor contract Down, not weeks later near receiver build
        assert load.movement.depart_after <= down_a + timedelta(days=2)
        assert load.movement.depart_after >= down_a - timedelta(hours=1)
