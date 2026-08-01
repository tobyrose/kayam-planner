from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import CrewMember, Location, LorryType
from app.models.costing import LoadCostAllocation, SupplierInvoice
from app.models.crew_movements import CrewMovement, CrewMovementPassenger
from app.models.crew_planning import CrewAssignment
from app.models.jobs import Job
from app.models.logistics import EstimateSource
from app.services.costing import CostingError, CostingService
from app.services.logistics import LogisticsService


def test_labour_and_travel_estimates(session: Session) -> None:
    seed_development_data(session)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    crew = session.scalar(select(CrewMember))
    assert job is not None and crew is not None
    crew.hourly_cost = Decimal("20")
    crew.travel_hourly_cost = Decimal("10")
    phase = job.phases[0]
    session.add(
        CrewAssignment(
            job_phase_id=phase.id,
            crew_member_id=crew.id,
            start_at=phase.start_at,
            end_at=phase.start_at + timedelta(hours=8),
            role="Crew",
        )
    )
    origin = session.scalar(select(Location).where(Location.id != job.location_id))
    assert origin is not None
    movement = CrewMovement(
        movement_code="COST-CM",
        origin_location_id=origin.id,
        destination_location_id=job.location_id,
        depart_after=phase.start_at - timedelta(hours=5),
        arrive_by=phase.start_at - timedelta(hours=1),
    )
    session.add(movement)
    session.flush()
    session.add(CrewMovementPassenger(crew_movement_id=movement.id, crew_member_id=crew.id))
    session.commit()

    service = CostingService(session)
    assert service.crew_work_cost(job.id) == Decimal("160.00")
    assert service.crew_travel_cost(job) == Decimal("40.00")


def test_load_estimate_manual_override_and_invoice_allocation(session: Session) -> None:
    seed_development_data(session)
    locations = session.scalars(select(Location).order_by(Location.id)).all()
    lorry_type = session.scalar(select(LorryType))
    assert lorry_type is not None
    lorry_type.default_cost_per_km = Decimal("2")
    lorry_type.minimum_load_cost = Decimal("100")
    logistics = LogisticsService(session)
    start = datetime(2026, 5, 1, tzinfo=UTC)
    movement = logistics.create_movement(
        {
            "movement_code": "COST-MV",
            "origin_location_id": locations[0].id,
            "destination_location_id": locations[1].id,
            "depart_after": start,
            "arrive_by": start + timedelta(hours=4),
        }
    )
    load = logistics.create_load(
        {
            "equipment_movement_id": movement.id,
            "load_number": 1,
            "lorry_type_id": lorry_type.id,
            "estimated_distance_km": Decimal("80"),
        }
    )
    service = CostingService(session)
    assert service.calculate_load_estimate(load) == Decimal("160")
    service.set_manual_load_estimate(load, Decimal("125"))
    assert load.estimate_source == EstimateSource.MANUAL
    assert service.calculate_load_estimate(load) == Decimal("125")

    invoice = SupplierInvoice(
        supplier_reference="INV-1",
        supplier_name="Test Haulage",
        invoice_date=date(2026, 5, 2),
        total_amount=Decimal("200"),
    )
    session.add(invoice)
    session.commit()
    service.allocate_invoice(
        invoice,
        [
            LoadCostAllocation(
                supplier_invoice_id=invoice.id,
                load_id=load.id,
                allocated_amount=Decimal("150"),
            )
        ],
    )
    assert service.load_actual_cost(load.id) == Decimal("150")
    assert service.load_variance(load) == Decimal("25")
    with pytest.raises(CostingError):
        service.allocate_invoice(
            invoice,
            [
                LoadCostAllocation(
                    supplier_invoice_id=invoice.id,
                    load_id=load.id,
                    allocated_amount=Decimal("60"),
                )
            ],
        )


def test_job_margin(session: Session) -> None:
    seed_development_data(session)
    job = session.scalar(select(Job).where(Job.job_code == "DEMO-ROS-26"))
    assert job is not None
    job.contract_revenue = Decimal("1000")
    summary = CostingService(session).job_summary(job)
    assert summary.estimated_margin <= Decimal("1000")
    assert summary.actual_margin is None
