from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.costing import LoadCostAllocation, SupplierInvoice
from app.models.crew_movements import CrewMovement, CrewMovementPassenger
from app.models.crew_planning import CrewAssignment
from app.models.jobs import Job, JobPhase
from app.models.logistics import EstimateSource, Load


@dataclass(frozen=True)
class JobCostSummary:
    revenue: Decimal
    labour_estimate: Decimal
    travel_estimate: Decimal
    load_estimate: Decimal
    actual_cost: Decimal
    estimated_margin: Decimal
    actual_margin: Decimal | None


class CostingError(Exception):
    pass


class CostingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def crew_work_cost(self, job_id: int) -> Decimal:
        assignments = self.session.scalars(
            select(CrewAssignment)
            .join(CrewAssignment.job_phase)
            .where(JobPhase.job_id == job_id, CrewAssignment.crew_member_id.is_not(None))
        )
        total = Decimal(0)
        for assignment in assignments:
            assert assignment.crew_member is not None
            hours = Decimal(str((assignment.end_at - assignment.start_at) / timedelta(hours=1)))
            total += hours * assignment.crew_member.hourly_cost
        return total.quantize(Decimal("0.01"))

    def crew_travel_cost(self, job: Job) -> Decimal:
        movements = self.session.scalars(
            select(CrewMovement).where(
                (CrewMovement.origin_location_id == job.location_id)
                | (CrewMovement.destination_location_id == job.location_id)
            )
        )
        total = Decimal(0)
        for movement in movements:
            hours = Decimal(str((movement.arrive_by - movement.depart_after) / timedelta(hours=1)))
            passengers = self.session.scalars(
                select(CrewMovementPassenger).where(
                    CrewMovementPassenger.crew_movement_id == movement.id,
                    CrewMovementPassenger.crew_member_id.is_not(None),
                )
            )
            for passenger in passengers:
                assert passenger.crew_member is not None
                total += hours * passenger.crew_member.travel_hourly_cost
        return total.quantize(Decimal("0.01"))

    def calculate_load_estimate(self, load: Load) -> Decimal:
        if load.estimate_source == EstimateSource.MANUAL:
            return load.estimated_cost
        estimate = max(
            load.lorry_type.minimum_load_cost,
            load.estimated_distance_km * load.lorry_type.default_cost_per_km,
        )
        load.estimated_cost = estimate
        return estimate

    def set_manual_load_estimate(self, load: Load, amount: Decimal) -> None:
        if amount < 0:
            raise CostingError("Estimate cannot be negative")
        load.estimated_cost = amount
        load.estimate_source = EstimateSource.MANUAL
        self.session.commit()

    def load_actual_cost(self, load_id: int) -> Decimal:
        allocated = self.session.scalar(
            select(func.coalesce(func.sum(LoadCostAllocation.allocated_amount), 0)).where(
                LoadCostAllocation.load_id == load_id
            )
        )
        return Decimal(allocated or 0)

    def load_variance(self, load: Load) -> Decimal | None:
        actual = self.load_actual_cost(load.id)
        if actual == 0 and load.actual_cost == 0:
            return None
        actual = actual or load.actual_cost
        return actual - self.calculate_load_estimate(load)

    def allocate_invoice(
        self, invoice: SupplierInvoice, allocations: list[LoadCostAllocation]
    ) -> None:
        proposed = sum((item.allocated_amount for item in allocations), Decimal(0))
        existing = self.session.scalar(
            select(func.coalesce(func.sum(LoadCostAllocation.allocated_amount), 0)).where(
                LoadCostAllocation.supplier_invoice_id == invoice.id
            )
        )
        if Decimal(existing or 0) + proposed > invoice.total_amount:
            raise CostingError("Invoice allocations exceed the invoice total")
        self.session.add_all(allocations)
        self.session.commit()

    def job_summary(self, job: Job) -> JobCostSummary:
        labour = self.crew_work_cost(job.id)
        travel = self.crew_travel_cost(job)
        relevant_loads = self.session.scalars(
            select(Load)
            .join(Load.movement)
            .where(
                (Load.movement.has(origin_location_id=job.location_id))
                | (Load.movement.has(destination_location_id=job.location_id))
            )
        ).all()
        loads = sum((self.calculate_load_estimate(load) for load in relevant_loads), Decimal(0))
        actual = self.session.scalar(
            select(func.coalesce(func.sum(LoadCostAllocation.allocated_amount), 0)).where(
                LoadCostAllocation.job_id == job.id
            )
        )
        actual_cost = Decimal(actual or 0)
        estimate_total = labour + travel + loads
        has_actuals = actual_cost > 0
        return JobCostSummary(
            revenue=job.contract_revenue,
            labour_estimate=labour,
            travel_estimate=travel,
            load_estimate=loads,
            actual_cost=actual_cost,
            estimated_margin=job.contract_revenue - estimate_total,
            actual_margin=job.contract_revenue - actual_cost if has_actuals else None,
        )
