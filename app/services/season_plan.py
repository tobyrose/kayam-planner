"""Whole-season load design and crew-move autofill (V1).

Planner-triggered: clear unlocked auto-generated plans, then:

1. For each job (earliest Build first), cover remaining *section + pole* shortfall with loads.
   Prefer stock freed from an earlier job (job→job); otherwise ship from the Yard.
   (Linked kit is implied by sections/poles — shown on the load sheet, not packed as separate
   trailer lines in V1.)
2. Pack each origin→destination batch into Flat (preferred) lorries by loading points (Q042).
3. Schedule arrival on the first Build day (after receiving crew when Tentmaster assigned).
4. Job→job leaves at the donor's contract Down (not just-in-time).
5. After the last use of each batch, ship remaining free stock **back to the Yard**.
6. Auto-create crew moves between consecutive Tentmaster phases at different sites.

Does **not** do spare-capacity hitchhiking, full multi-leg optimisation, or asset-level
assignment — quantity-by-type only. Locked movements/loads and non-auto crew moves are kept.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.administration import Location, LocationType, LorryType, Tentmaster
from app.models.jobs import Job, JobEquipmentRequirement, JobPhase, PhaseType, RecordSource
from app.models.logistics import (
    EquipmentMovement,
    Load,
    LoadItem,
    LoadStatus,
    MovementStatus,
)
from app.models.crew_movements import CrewJourneyLeg, CrewMovement, JourneyMode
from app.services.jobs import BREAK_TRAIL_DAYS, BUILD_LEAD_DAYS
from app.services.section_coverage import loadable_delivered, loadable_requirements

AUTO_NOTES = "AUTO-GENERATED season plan — re-run replaces unlocked auto plans"
DEFAULT_TRAVEL_HOURS = 24.0
MIN_TRAVEL_HOURS = 6.0
TRUCK_KMH = 50.0
OPERATIONAL_HOURS_PAD = 4.0


@dataclass
class SeasonPlanResult:
    movements_created: int = 0
    loads_created: int = 0
    load_items_created: int = 0
    crew_moves_created: int = 0
    auto_loads_removed: int = 0
    auto_crew_moves_removed: int = 0
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [
            f"{self.loads_created} loads",
            f"{self.movements_created} movements",
            f"{self.crew_moves_created} crew moves",
        ]
        if self.auto_loads_removed:
            parts.append(f"removed {self.auto_loads_removed} old auto loads")
        if self.auto_crew_moves_removed:
            parts.append(f"removed {self.auto_crew_moves_removed} old auto crew moves")
        text = "Season plan: " + ", ".join(parts) + "."
        if self.warnings:
            text += " Warnings: " + "; ".join(self.warnings[:8])
            if len(self.warnings) > 8:
                text += f" (+{len(self.warnings) - 8} more)"
        return text


def _job_window(job: Job) -> tuple[datetime, datetime] | None:
    if not job.tent_requirements:
        return None
    starts = [
        tent.contracted_up_at - timedelta(days=BUILD_LEAD_DAYS)
        for tent in job.tent_requirements
    ]
    ends = [
        tent.contracted_down_at + timedelta(days=BREAK_TRAIL_DAYS)
        for tent in job.tent_requirements
    ]
    return min(starts), max(ends)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _travel_hours(origin: Location, destination: Location) -> float:
    if (
        origin.latitude is None
        or origin.longitude is None
        or destination.latitude is None
        or destination.longitude is None
    ):
        return DEFAULT_TRAVEL_HOURS
    km = _haversine_km(
        float(origin.latitude),
        float(origin.longitude),
        float(destination.latitude),
        float(destination.longitude),
    )
    return max(MIN_TRAVEL_HOURS, km / TRUCK_KMH + OPERATIONAL_HOURS_PAD)


def _points_for_type(equipment_type) -> Decimal:
    """Loading points; SC/unknown sections default so they still ship; poles use Q042 or 1.2."""
    points = equipment_type.section_capacity_units or Decimal(0)
    if points > 0:
        return points
    if equipment_type.code in {"VOE", "VNE"}:
        return Decimal("7.2")  # one end ≈ one Flatbed (Valhalla rule of thumb)
    if equipment_type.code == "V":
        return Decimal("3.6")  # two middles per Flatbed
    if equipment_type.category == "pole":
        return Decimal("1.2")  # same as Kayam King Pole pair when unconfigured
    if equipment_type.category == "section":
        return Decimal("1.0")
    return Decimal(0)


def _pack_quantities(
    needed: dict[str, int],
    points_by_code: dict[str, Decimal],
    capacity: Decimal,
) -> list[dict[str, int]]:
    """First-fit decreasing pack of type quantities into lorries of `capacity` points."""
    units: list[tuple[str, Decimal]] = []
    for code, qty in sorted(needed.items(), key=lambda item: -float(points_by_code.get(item[0], 1))):
        point = points_by_code.get(code, Decimal(1))
        for _ in range(qty):
            units.append((code, point))
    units.sort(key=lambda item: item[1], reverse=True)
    loads: list[dict[str, int]] = []
    remaining: list[Decimal] = []
    for code, point in units:
        placed = False
        for index, free in enumerate(remaining):
            if free >= point:
                remaining[index] = free - point
                loads[index][code] = loads[index].get(code, 0) + 1
                placed = True
                break
        if not placed:
            # Oversized single item still gets its own lorry.
            loads.append({code: 1})
            remaining.append(max(Decimal(0), capacity - point))
    return loads


class SeasonPlanService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def generate(self, *, include_crew_moves: bool = True) -> SeasonPlanResult:
        result = SeasonPlanResult()
        yard = self.session.scalar(
            select(Location).where(Location.location_type == LocationType.YARD)
        )
        if yard is None:
            result.warnings.append("No yard location found — cannot generate loads.")
            return result

        flat = self.session.scalar(
            select(LorryType).where(LorryType.name == "Flat", LorryType.active.is_(True))
        )
        curtain = self.session.scalar(
            select(LorryType).where(LorryType.name == "Curtain", LorryType.active.is_(True))
        )
        lorry_type = flat or curtain
        if lorry_type is None:
            result.warnings.append("No Flat/Curtain lorry type — cannot generate loads.")
            return result
        capacity = lorry_type.section_capacity_units or Decimal("7.2")

        result.auto_loads_removed = self._clear_unlocked_auto_loads()
        if include_crew_moves:
            result.auto_crew_moves_removed = self._clear_unlocked_auto_crew_moves()

        jobs = list(
            self.session.scalars(
                select(Job)
                .options(
                    selectinload(Job.location),
                    selectinload(Job.tent_requirements),
                    selectinload(Job.phases),
                    selectinload(Job.equipment_requirements).selectinload(
                        JobEquipmentRequirement.equipment_type
                    ),
                )
                .order_by(Job.id)
            )
        )
        jobs = [job for job in jobs if job.tent_requirements]
        jobs.sort(key=lambda job: (_job_window(job) or (datetime.max, datetime.max))[0])

        # Free section stock after a job's break starts: location_id -> {code: qty}
        free_pool: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # When stock became free at that location (break start of donor job)
        free_since: dict[int, datetime] = {}

        existing_loads = self._existing_loads_by_job(jobs)

        next_load_number = self._next_load_number()
        next_mv = self._next_movement_index()

        for job in jobs:
            window = _job_window(job)
            if window is None:
                continue
            required = loadable_requirements(job)
            if not required:
                continue
            already = loadable_delivered(existing_loads.get(job.id, []))
            shortfall: dict[str, int] = {}
            for code, need in required.items():
                have = already.get(code, 0)
                if have < need:
                    shortfall[code] = need - have
            if not shortfall:
                self._release_to_pool(job, required, free_pool, free_since)
                continue

            # Loads must arrive on (or as near as possible to) the **first Build day**,
            # not on contract Up — kit is needed for the build.
            build_start = window[0]
            crew_ready = self._crew_ready_at(job)
            # Prefer morning of first build day; if crew only arrives later that day, after crew.
            arrive_by = build_start + timedelta(hours=10)  # ~10:00 on first build day
            if crew_ready is not None and crew_ready.date() == build_start.date():
                arrive_by = max(arrive_by, crew_ready + timedelta(hours=1))
            elif crew_ready is not None and crew_ready > arrive_by:
                # Crew not on site until after build start — still aim for build day, warn.
                result.warnings.append(
                    f"{job.job_code}: crew on site {crew_ready:%d %b %H:%M} — "
                    "loads still aimed at first Build day"
                )
            if crew_ready is None:
                result.warnings.append(
                    f"{job.job_code}: no Tentmaster on phases — loads timed to first Build day"
                )

            # Pull from free pool (job→job), earliest free first, then yard for the rest.
            remaining = dict(shortfall)
            # Donor locations with free stock, sorted by free_since
            donors = sorted(
                (
                    (loc_id, free_since.get(loc_id, window[0]), dict(stock))
                    for loc_id, stock in free_pool.items()
                    if loc_id != job.location_id and any(stock.get(c, 0) > 0 for c in remaining)
                ),
                key=lambda item: item[1],
            )
            for loc_id, available_from, stock in donors:
                batch: dict[str, int] = {}
                for code, need in list(remaining.items()):
                    take = min(need, stock.get(code, 0))
                    if take <= 0:
                        continue
                    batch[code] = take
                if not batch:
                    continue
                origin = self.session.get(Location, loc_id)
                if origin is None:
                    continue
                hours = _travel_hours(origin, job.location)
                # Leave the donor site when stock becomes free (contract Down / break), not
                # weeks later when the next gig wants it — kit must not sit on an empty site.
                depart = available_from + timedelta(hours=4)
                arrive = depart + timedelta(hours=hours)
                # Must still be on site for the destination's first Build day (early is fine).
                if arrive.date() > arrive_by.date():
                    result.warnings.append(
                        f"{job.job_code}: skip job→job from {origin.name} "
                        f"(would arrive {arrive:%d %b}, after first Build {arrive_by:%d %b})"
                    )
                    continue
                for code, take in batch.items():
                    remaining[code] = remaining.get(code, 0) - take
                    if remaining.get(code, 0) <= 0:
                        remaining.pop(code, None)
                    free_pool[loc_id][code] -= take
                created = self._create_packed_loads(
                    origin=origin,
                    destination=job.location,
                    batch=batch,
                    depart=depart,
                    arrive=arrive,
                    lorry_type=lorry_type,
                    capacity=capacity,
                    next_load_number=next_load_number,
                    next_mv=next_mv,
                    job_code=job.job_code,
                )
                next_load_number += created[0]
                next_mv += created[1]
                result.loads_created += created[0]
                result.movements_created += created[1]
                result.load_items_created += created[2]

            if remaining:
                hours = _travel_hours(yard, job.location)
                depart = arrive_by - timedelta(hours=hours)
                if arrive_by <= depart:
                    arrive_by = depart + timedelta(hours=max(MIN_TRAVEL_HOURS, hours))
                created = self._create_packed_loads(
                    origin=yard,
                    destination=job.location,
                    batch=remaining,
                    depart=depart,
                    arrive=arrive_by,
                    lorry_type=lorry_type,
                    capacity=capacity,
                    next_load_number=next_load_number,
                    next_mv=next_mv,
                    job_code=job.job_code,
                )
                next_load_number += created[0]
                next_mv += created[1]
                result.loads_created += created[0]
                result.movements_created += created[1]
                result.load_items_created += created[2]

            self._release_to_pool(job, required, free_pool, free_since)

        # Everything left on site after its last job goes back to the Yard.
        returned = self._return_free_stock_to_yard(
            yard=yard,
            free_pool=free_pool,
            free_since=free_since,
            lorry_type=lorry_type,
            capacity=capacity,
            next_load_number=next_load_number,
            next_mv=next_mv,
            result=result,
        )
        next_load_number += returned[0]
        next_mv += returned[1]

        if include_crew_moves:
            result.crew_moves_created = self._generate_crew_moves(result.warnings)

        self.session.commit()
        return result

    def _return_free_stock_to_yard(
        self,
        *,
        yard: Location,
        free_pool: dict[int, dict[str, int]],
        free_since: dict[int, datetime],
        lorry_type: LorryType,
        capacity: Decimal,
        next_load_number: int,
        next_mv: int,
        result: SeasonPlanResult,
    ) -> tuple[int, int]:
        """Ship any stock still sitting at a site after the season plan back to the Yard.

        Returns (loads_created, movements_created) for caller load-number bookkeeping.
        """
        loads_n = 0
        moves_n = 0
        # Stable order: earliest free first so return load numbers roughly follow season flow
        sites = sorted(
            (
                (loc_id, free_since.get(loc_id), dict(stock))
                for loc_id, stock in free_pool.items()
                if loc_id != yard.id and any(qty > 0 for qty in stock.values())
            ),
            key=lambda item: (
                item[1].timestamp() if item[1] is not None else float("-inf"),
                item[0],
            ),
        )
        for loc_id, available_from, stock in sites:
            batch = {code: qty for code, qty in stock.items() if qty > 0}
            if not batch:
                continue
            origin = self.session.get(Location, loc_id)
            if origin is None:
                continue
            if available_from is None:
                result.warnings.append(
                    f"Return to yard from {origin.name}: no free-since time — skipped"
                )
                continue
            hours = _travel_hours(origin, yard)
            depart = available_from + timedelta(hours=4)
            arrive = depart + timedelta(hours=max(MIN_TRAVEL_HOURS, hours))
            created = self._create_packed_loads(
                origin=origin,
                destination=yard,
                batch=batch,
                depart=depart,
                arrive=arrive,
                lorry_type=lorry_type,
                capacity=capacity,
                next_load_number=next_load_number + loads_n,
                next_mv=next_mv + moves_n,
                job_code="YARD-RETURN",
            )
            loads_n += created[0]
            moves_n += created[1]
            result.loads_created += created[0]
            result.movements_created += created[1]
            result.load_items_created += created[2]
            for code in batch:
                free_pool[loc_id][code] = 0
        return loads_n, moves_n

    def _release_to_pool(
        self,
        job: Job,
        required: dict[str, int],
        free_pool: dict[int, dict[str, int]],
        free_since: dict[int, datetime],
    ) -> None:
        break_start = max(tent.contracted_down_at for tent in job.tent_requirements)
        free_since[job.location_id] = max(
            free_since.get(job.location_id, break_start), break_start
        )
        for code, qty in required.items():
            free_pool[job.location_id][code] += qty

    def _crew_ready_at(self, job: Job) -> datetime | None:
        """Earliest start among phases that have a Tentmaster (crew on site)."""
        dated = [
            phase.start_at
            for phase in job.phases
            if phase.tentmaster_id is not None
            and phase.phase_type in {PhaseType.BUILD, PhaseType.UP, PhaseType.BREAK}
        ]
        return min(dated) if dated else None

    def _create_packed_loads(
        self,
        *,
        origin: Location,
        destination: Location,
        batch: dict[str, int],
        depart: datetime,
        arrive: datetime,
        lorry_type: LorryType,
        capacity: Decimal,
        next_load_number: int,
        next_mv: int,
        job_code: str,
    ) -> tuple[int, int, int]:
        """Returns (loads_created, movements_created, items_created)."""
        if origin.id == destination.id or not batch:
            return 0, 0, 0
        # Resolve points for codes via a small type lookup
        from app.models.administration import EquipmentType

        types = {
            t.code: t
            for t in self.session.scalars(
                select(EquipmentType).where(EquipmentType.code.in_(batch.keys()))
            )
        }
        points_by_code = {
            code: _points_for_type(types[code]) for code in batch if code in types
        }
        # Drop unknown codes
        clean = {code: qty for code, qty in batch.items() if code in types and qty > 0}
        if not clean:
            return 0, 0, 0
        packs = _pack_quantities(clean, points_by_code, capacity)
        loads_n = 0
        items_n = 0
        load_num = next_load_number
        mv_index = next_mv
        for pack in packs:
            if arrive <= depart:
                arrive_use = depart + timedelta(hours=MIN_TRAVEL_HOURS)
            else:
                arrive_use = arrive
            movement = EquipmentMovement(
                movement_code=f"MV-AUTO-{mv_index:04d}",
                origin_location_id=origin.id,
                destination_location_id=destination.id,
                depart_after=depart,
                arrive_by=arrive_use,
                status=MovementStatus.PLANNED,
                source=RecordSource.GENERATED,
                notes=f"{AUTO_NOTES} → {job_code}",
            )
            self.session.add(movement)
            self.session.flush()
            load = Load(
                equipment_movement_id=movement.id,
                load_number=load_num,
                lorry_type_id=lorry_type.id,
                status=LoadStatus.PLANNED,
                planned_departure_at=depart,
                planned_arrival_at=arrive_use,
                notes=f"{AUTO_NOTES} → {job_code}",
            )
            self.session.add(load)
            self.session.flush()
            for code, qty in pack.items():
                self.session.add(
                    LoadItem(
                        load_id=load.id,
                        equipment_type_id=types[code].id,
                        quantity=qty,
                    )
                )
                items_n += 1
            loads_n += 1
            load_num += 1
            mv_index += 1
        return loads_n, loads_n, items_n  # one movement per load in V1

    def _existing_loads_by_job(self, jobs: list[Job]) -> dict[int, list[Load]]:
        loads = self.session.scalars(
            select(Load).options(
                selectinload(Load.movement),
                selectinload(Load.items).selectinload(LoadItem.equipment_type),
                selectinload(Load.items).selectinload(LoadItem.equipment_asset),
            )
        ).all()
        by_job: dict[int, list[Load]] = defaultdict(list)
        for load in loads:
            movement = load.movement
            for job in jobs:
                window = _job_window(job)
                if window is None:
                    continue
                if (
                    job.location_id == movement.destination_location_id
                    and window[0] - timedelta(days=3)
                    <= movement.arrive_by
                    <= window[1]
                ):
                    by_job[job.id].append(load)
                    break
        return by_job

    def _clear_unlocked_auto_loads(self) -> int:
        movements = self.session.scalars(
            select(EquipmentMovement)
            .where(
                EquipmentMovement.source == RecordSource.GENERATED,
                EquipmentMovement.locked.is_(False),
            )
            .options(selectinload(EquipmentMovement.loads))
        ).all()
        removed = 0
        for movement in movements:
            if any(load.locked for load in movement.loads):
                continue
            removed += len(movement.loads)
            self.session.delete(movement)
        self.session.flush()
        return removed

    def _clear_unlocked_auto_crew_moves(self) -> int:
        moves = self.session.scalars(
            select(CrewMovement).where(
                CrewMovement.locked.is_(False),
                CrewMovement.notes.is_not(None),
            )
        ).all()
        removed = 0
        for move in moves:
            if move.notes and AUTO_NOTES in move.notes:
                self.session.delete(move)
                removed += 1
        self.session.flush()
        return removed

    def _generate_crew_moves(self, warnings: list[str]) -> int:
        created = 0
        tentmasters = self.session.scalars(
            select(Tentmaster).where(Tentmaster.active.is_(True))
        ).all()
        existing = list(self.session.scalars(select(CrewMovement)).all())
        cm_index = 1
        for tentmaster in tentmasters:
            phases = self.session.scalars(
                select(JobPhase)
                .where(JobPhase.tentmaster_id == tentmaster.id)
                .options(selectinload(JobPhase.job).selectinload(Job.location))
                .order_by(JobPhase.start_at)
            ).all()
            # Collapse to job visits in order (use outermost phase span per consecutive job)
            visits: list[tuple[Job, datetime, datetime]] = []
            for phase in phases:
                job = phase.job
                if visits and visits[-1][0].id == job.id:
                    prev_job, start, end = visits[-1]
                    visits[-1] = (prev_job, min(start, phase.start_at), max(end, phase.end_at))
                else:
                    visits.append((job, phase.start_at, phase.end_at))
            for index in range(len(visits) - 1):
                job_a, _start_a, end_a = visits[index]
                job_b, start_b, _end_b = visits[index + 1]
                if job_a.location_id == job_b.location_id:
                    continue
                if start_b <= end_a:
                    continue
                # Skip if a crew move already covers this handoff (any non-deleted).
                if any(
                    move.tentmaster_id == tentmaster.id
                    and move.origin_location_id == job_a.location_id
                    and move.destination_location_id == job_b.location_id
                    and move.depart_after >= end_a - timedelta(days=1)
                    and move.arrive_by <= start_b + timedelta(days=1)
                    for move in existing
                ):
                    continue
                hours = _travel_hours(job_a.location, job_b.location)
                depart = end_a
                arrive = start_b - timedelta(hours=1)
                if arrive <= depart:
                    arrive = depart + timedelta(hours=max(MIN_TRAVEL_HOURS, hours))
                    if arrive > start_b:
                        warnings.append(
                            f"Crew {tentmaster.name}: tight turnaround "
                            f"{job_a.job_code} → {job_b.job_code}"
                        )
                code = f"CM-AUTO-{cm_index:04d}"
                while self.session.scalar(
                    select(CrewMovement.id).where(CrewMovement.movement_code == code)
                ):
                    cm_index += 1
                    code = f"CM-AUTO-{cm_index:04d}"
                movement = CrewMovement(
                    movement_code=code,
                    origin_location_id=job_a.location_id,
                    destination_location_id=job_b.location_id,
                    tentmaster_id=tentmaster.id,
                    depart_after=depart,
                    arrive_by=arrive,
                    status=MovementStatus.PLANNED,
                    notes=f"{AUTO_NOTES} · {tentmaster.name} · {job_a.job_code}→{job_b.job_code}",
                )
                self.session.add(movement)
                self.session.flush()
                movement.legs.append(
                    CrewJourneyLeg(
                        sequence=1,
                        mode=JourneyMode.VAN,
                        origin_label=job_a.location.name,
                        destination_label=job_b.location.name,
                        depart_at=depart,
                        arrive_at=arrive,
                    )
                )
                existing.append(movement)
                created += 1
                cm_index += 1
        return created

    def _next_load_number(self) -> int:
        max_n = self.session.scalar(select(func.max(Load.load_number)))
        return int(max_n or 0) + 1

    def _next_movement_index(self) -> int:
        count = self.session.scalar(select(func.count()).select_from(EquipmentMovement)) or 0
        return int(count) + 1
