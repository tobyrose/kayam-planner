from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models.administration import Location, LocationType
from app.models.jobs import Job, JobTentRequirement, JobTentSection
from app.models.logistics import EquipmentMovement, Load, LoadItem
from app.services.jobs import BREAK_TRAIL_DAYS, BUILD_LEAD_DAYS

LABEL_WIDTH = 140
LANE_WIDTH = 170
ROW_HEIGHT = 44

_HUB_TYPES = {LocationType.YARD, LocationType.DEPOT}


@dataclass(frozen=True)
class FlowNode:
    location_id: int
    name: str
    x: int


@dataclass(frozen=True)
class FlowCellBlock:
    job_id: int
    label: str
    subtitle: str
    href: str
    status: str
    segment: str


@dataclass(frozen=True)
class FlowDay:
    day: date
    cells: dict[int, list[FlowCellBlock]]


@dataclass(frozen=True)
class FlowEdge:
    movement_id: int
    href: str
    label: str
    subtitle: str
    status: str
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class FlowData:
    start: date
    end: date
    label_width: int
    lane_width: int
    row_height: int
    width: int
    height: int
    nodes: list[FlowNode]
    days: list[FlowDay]
    edges: list[FlowEdge]

    def jsonable(self) -> dict[str, object]:
        return asdict(self)


def _last_day(end_at: datetime) -> date:
    """Last calendar day a half-open [start, end) span actually touches."""
    return (end_at - timedelta(microseconds=1)).date()


def _segment(day: date, span_start: date, span_end: date) -> str:
    is_start = day == span_start
    is_end = day == span_end
    if is_start and is_end:
        return "solo"
    if is_start:
        return "start"
    if is_end:
        return "end"
    return "mid"


def _tent_summary(job: Job) -> str:
    codes = [
        requirement.sequence_code
        for requirement in job.tent_requirements
        if requirement.sequence_code
    ]
    return ", ".join(codes)


def _job_window(job: Job) -> tuple[datetime, datetime]:
    """Earliest tent's Build start to latest tent's Break end. `job.tent_requirements` must be
    non-empty — only called for jobs matched by a query that already requires at least one."""
    starts = [
        requirement.contracted_up_at - timedelta(days=BUILD_LEAD_DAYS)
        for requirement in job.tent_requirements
    ]
    ends = [
        requirement.contracted_down_at + timedelta(days=BREAK_TRAIL_DAYS)
        for requirement in job.tent_requirements
    ]
    return min(starts), max(ends)


def _item_summary(load: Load) -> list[str]:
    labels = []
    for item in load.items:
        if item.equipment_asset is not None:
            labels.append(item.equipment_asset.asset_code)
        elif item.equipment_type is not None:
            labels.append(f"{item.quantity}× {item.equipment_type.code}")
    return labels


class FlowService:
    """Build the loads/equipment flow diagram from bounded range queries.

    Same principle as BoardService (D027): assemble everything server-side from a
    handful of date-bounded queries; the browser only renders, highlights, and
    launches server-backed edits. Laid out like the season board — dates run down
    the side — but columns are locations, not Tentmasters: each column shows the
    job (and its booked tent sections) sitting at that location on that date, and
    a load's journey is drawn as a line connecting its origin and destination
    columns at the correct depart/arrival dates.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def build(self, start: date, end: date) -> FlowData:
        if end < start or (end - start).days > 370:
            raise ValueError("Flow range must be ordered and no longer than 370 days")
        timezone = ZoneInfo(get_settings().default_timezone)
        range_start = datetime.combine(start, time.min, timezone)
        range_end = datetime.combine(end + timedelta(days=1), time.min, timezone)

        movements = self.session.scalars(
            select(EquipmentMovement)
            .where(
                EquipmentMovement.depart_after < range_end,
                EquipmentMovement.arrive_by > range_start,
            )
            .options(
                selectinload(EquipmentMovement.origin),
                selectinload(EquipmentMovement.destination),
                selectinload(EquipmentMovement.loads)
                .selectinload(Load.items)
                .selectinload(LoadItem.equipment_asset),
                selectinload(EquipmentMovement.loads)
                .selectinload(Load.items)
                .selectinload(LoadItem.equipment_type),
            )
            .order_by(EquipmentMovement.depart_after)
        ).all()
        jobs = self.session.scalars(
            select(Job)
            .join(Job.tent_requirements)
            .where(
                JobTentRequirement.contracted_up_at
                < range_end + timedelta(days=BUILD_LEAD_DAYS),
                JobTentRequirement.contracted_down_at
                > range_start - timedelta(days=BREAK_TRAIL_DAYS),
            )
            .distinct()
            .options(
                selectinload(Job.location),
                selectinload(Job.tent_requirements)
                .selectinload(JobTentRequirement.sections)
                .selectinload(JobTentSection.equipment_type),
            )
        ).all()

        locations: dict[int, Location] = {}
        for movement in movements:
            locations[movement.origin_location_id] = movement.origin
            locations[movement.destination_location_id] = movement.destination
        for job in jobs:
            locations[job.location_id] = job.location

        ordered_locations = sorted(
            locations.values(),
            key=lambda location: (
                0 if location.location_type in _HUB_TYPES else 1,
                location.name,
            ),
        )
        node_x = {
            location.id: LABEL_WIDTH + index * LANE_WIDTH + LANE_WIDTH // 2
            for index, location in enumerate(ordered_locations)
        }
        nodes = [
            FlowNode(location.id, location.name, node_x[location.id])
            for location in ordered_locations
        ]

        def row_y(moment: date) -> int:
            offset_days = (moment - start).days
            return offset_days * ROW_HEIGHT + ROW_HEIGHT // 2

        span_days = (end - start).days + 1
        days = []
        for offset in range(span_days):
            day = start + timedelta(days=offset)
            cells: dict[int, list[FlowCellBlock]] = {}
            for job in jobs:
                window_start, window_end = _job_window(job)
                span_start = window_start.date()
                span_end = _last_day(window_end)
                if not (span_start <= day <= span_end):
                    continue
                tent_summary = _tent_summary(job)
                cells.setdefault(job.location_id, []).append(
                    FlowCellBlock(
                        job.id,
                        job.job_code,
                        tent_summary or job.name,
                        f"/jobs/{job.id}",
                        job.commercial_status.value,
                        _segment(day, span_start, span_end),
                    )
                )
            days.append(FlowDay(day, cells))

        edges: list[FlowEdge] = []
        for movement in movements:
            if movement.origin_location_id not in node_x:
                continue
            if movement.destination_location_id not in node_x:
                continue
            item_labels = sorted(
                {label for load in movement.loads for label in _item_summary(load)}
            )
            contents = ", ".join(item_labels) if item_labels else "no items recorded"
            first_load = movement.loads[0] if movement.loads else None
            route = f"{movement.origin.name} → {movement.destination.name}"
            edges.append(
                FlowEdge(
                    movement.id,
                    f"/loads/{first_load.id}" if first_load else "#",
                    f"{movement.movement_code} · {route}",
                    f"{len(movement.loads)} load(s) · {contents}",
                    movement.status.value,
                    node_x[movement.origin_location_id],
                    row_y(movement.depart_after.date()),
                    node_x[movement.destination_location_id],
                    row_y(_last_day(movement.arrive_by)),
                )
            )

        width = LABEL_WIDTH + len(nodes) * LANE_WIDTH
        height = span_days * ROW_HEIGHT
        return FlowData(
            start, end, LABEL_WIDTH, LANE_WIDTH, ROW_HEIGHT, width, height, nodes, days, edges
        )
