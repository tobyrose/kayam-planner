"""Loads Diagram — continuous job blocks, Yard column, labeled load arrows.

Design: LOAD_ENGINE_DESIGN.md §1. Job overlays span Build→Break as one block (not per-day cards).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models.administration import EquipmentAsset, EquipmentLink, Location, LocationType, Lorry
from app.models.jobs import Job, JobTentRequirement, JobTentSection
from app.models.logistics import EquipmentMovement, Load, LoadItem
from app.services.jobs import BREAK_TRAIL_DAYS, BUILD_LEAD_DAYS

LABEL_WIDTH = 72
JOB_LANE_WIDTH = 200
YARD_LANE_WIDTH = 110
HEADER_HEIGHT = 32
ROW_HEIGHT = 28
JOB_HEAD_HEIGHT = 32  # reserved for job name so arrivals don't cover it
LOAD_COLOR_COUNT = 12


@dataclass(frozen=True)
class FlowColumn:
    key: str
    kind: str  # yard | job
    label: str
    width: int
    x: int  # left pixel of column content


@dataclass(frozen=True)
class FlowLoadEvent:
    """A load arriving or departing on a specific day offset within a job block."""

    day_offset: int  # 0 = first day of job block
    kind: str  # arrival | departure
    text: str
    href: str
    load_id: int
    load_number: int
    color_index: int
    codes: str
    search: str
    full_contents: str
    origin_name: str
    dest_name: str
    depart_label: str
    arrive_label: str
    vehicle_type: str
    haulier_name: str
    stack_index: int = 0  # 0..n when several events share the same day+kind


@dataclass(frozen=True)
class FlowJobBlock:
    """One continuous job rectangle on the diagram."""

    job_id: int
    job_code: str
    subtitle: str
    status: str
    href: str
    pack_index: int
    left: int
    top: int
    width: int
    height: int
    span_days: int
    events: tuple[FlowLoadEvent, ...]
    # Contract Up window (earliest Up → latest Down) as px relative to block top
    up_offset: int = 0
    up_height: int = 0


@dataclass(frozen=True)
class FlowYardMark:
    """One Yard cell call-out — may list several loads leaving/arriving together."""

    day: date
    top: int
    kind: str  # yard_out | yard_in
    text: str
    href: str
    load_ids: tuple[int, ...]
    load_numbers: tuple[int, ...]
    color_index: int
    codes: str
    search: str
    full_contents: str
    origin_name: str
    dest_name: str
    depart_label: str
    arrive_label: str
    vehicle_type: str
    haulier_name: str


@dataclass(frozen=True)
class FlowEdge:
    """One arrow — may represent a convoy of loads on the same corridor/day."""

    load_ids: tuple[int, ...]
    load_numbers: tuple[int, ...]
    label: str  # e.g. "L7, L8, L9" or "L18–L21"
    href: str
    color_index: int
    x1: int
    y1: int
    x2: int
    y2: int
    lx: int
    ly: int
    label_width: int
    full_contents: str
    origin_name: str
    dest_name: str
    depart_label: str
    arrive_label: str
    vehicle_type: str
    haulier_name: str


@dataclass(frozen=True)
class FlowDay:
    day: date
    top: int


@dataclass(frozen=True)
class FlowData:
    start: date
    end: date
    label_width: int
    header_height: int
    row_height: int
    job_head_height: int
    width: int
    height: int
    columns: list[FlowColumn]
    days: list[FlowDay]
    job_blocks: list[FlowJobBlock]
    yard_marks: list[FlowYardMark]
    edges: list[FlowEdge]
    yard_stock_by_day: dict[str, dict[str, object]] = field(default_factory=dict)

    def jsonable(self) -> dict[str, object]:
        return asdict(self)


def _last_day(end_at: datetime) -> date:
    return (end_at - timedelta(microseconds=1)).date()


def _tent_summary(job: Job) -> str:
    return ", ".join(
        r.sequence_code for r in job.tent_requirements if r.sequence_code
    )


def _job_window(job: Job) -> tuple[datetime, datetime]:
    starts = [
        t.contracted_up_at - timedelta(days=BUILD_LEAD_DAYS) for t in job.tent_requirements
    ]
    ends = [
        t.contracted_down_at + timedelta(days=BREAK_TRAIL_DAYS) for t in job.tent_requirements
    ]
    return min(starts), max(ends)


def _up_window(job: Job) -> tuple[date, date] | None:
    """Contract Up period: earliest Up → latest Down (inclusive)."""
    if not job.tent_requirements:
        return None
    up0 = min(t.contracted_up_at for t in job.tent_requirements).date()
    down1 = max(t.contracted_down_at for t in job.tent_requirements).date()
    if down1 < up0:
        return None
    return up0, down1


def _item_labels(load: Load) -> list[str]:
    labels: list[str] = []
    for item in load.items:
        if item.equipment_asset is not None:
            labels.append(item.equipment_asset.asset_code)
        elif item.equipment_type is not None:
            labels.append(
                item.equipment_type.code
                if item.quantity == 1
                else f"{item.quantity}×{item.equipment_type.code}"
            )
    return labels


def _expand_load_contents(
    load: Load, links_by_parent: dict[int, list[tuple[str, int]]]
) -> str:
    primary = _item_labels(load)
    linked: dict[str, int] = defaultdict(int)
    for item in load.items:
        et = item.resolved_type
        qty = int(item.quantity)
        for child_code, per in links_by_parent.get(et.id, ()):
            linked[child_code] += per * qty
    parts = list(primary)
    if linked:
        parts.append(
            "linked: " + ", ".join(f"{c}×{n}" for c, n in sorted(linked.items()) if n)
        )
    return ", ".join(parts) if parts else "(empty)"


def _pack_job_columns(spans: dict[int, tuple[datetime, datetime]]) -> dict[int, int]:
    column_ends: list[datetime] = []
    assignment: dict[int, int] = {}
    for job_id, (start, end) in sorted(spans.items(), key=lambda i: i[1][0]):
        for index, column_end in enumerate(column_ends):
            if start >= column_end:
                column_ends[index] = end
                assignment[job_id] = index
                break
        else:
            column_ends.append(end)
            assignment[job_id] = len(column_ends) - 1
    return assignment


def _color_index(n: int) -> int:
    return (n - 1) % LOAD_COLOR_COUNT


def _format_load_list(numbers: list[int]) -> str:
    """Compact L# list: L7, L8, L9 or L18–L21 when consecutive."""
    if not numbers:
        return ""
    nums = sorted(set(numbers))
    if len(nums) == 1:
        return f"L{nums[0]}"
    consecutive = all(nums[i] == nums[0] + i for i in range(len(nums)))
    if consecutive and len(nums) >= 3:
        return f"L{nums[0]}–L{nums[-1]}"
    return ", ".join(f"L{n}" for n in nums)


def _label_width_px(label: str) -> int:
    # ~6.5px per char + padding
    return max(28, min(120, int(len(label) * 6.5) + 12))


class FlowService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def build(self, start: date, end: date) -> FlowData:
        if end < start or (end - start).days > 370:
            raise ValueError("Flow range must be ordered and no longer than 370 days")
        timezone = ZoneInfo(get_settings().default_timezone)
        range_start = datetime.combine(start, time.min, timezone)
        range_end = datetime.combine(end + timedelta(days=1), time.min, timezone)

        yard = self.session.scalar(
            select(Location).where(Location.location_type == LocationType.YARD)
        )

        links_by_parent: dict[int, list[tuple[str, int]]] = defaultdict(list)
        for link in self.session.scalars(
            select(EquipmentLink).options(selectinload(EquipmentLink.child_equipment_type))
        ):
            links_by_parent[link.parent_equipment_type_id].append(
                (link.child_equipment_type.code, int(link.quantity_per_parent))
            )

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
                .selectinload(LoadItem.equipment_asset)
                .selectinload(EquipmentAsset.equipment_type),
                selectinload(EquipmentMovement.loads)
                .selectinload(Load.items)
                .selectinload(LoadItem.equipment_type),
                selectinload(EquipmentMovement.loads).selectinload(Load.lorry_type),
                selectinload(EquipmentMovement.loads)
                .selectinload(Load.lorry)
                .selectinload(Lorry.haulier),
            )
            .order_by(EquipmentMovement.depart_after)
        ).all()

        jobs = [
            j
            for j in self.session.scalars(
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
            )
            if j.tent_requirements
        ]
        job_windows = {j.id: _job_window(j) for j in jobs}
        packed = _pack_job_columns(job_windows)
        pack_count = max(packed.values(), default=-1) + 1

        columns: list[FlowColumn] = []
        x = LABEL_WIDTH
        if yard is not None:
            columns.append(FlowColumn("yard", "yard", "Yard", YARD_LANE_WIDTH, x))
            x += YARD_LANE_WIDTH
        for index in range(pack_count):
            columns.append(FlowColumn(f"pack-{index}", "job", "", JOB_LANE_WIDTH, x))
            x += JOB_LANE_WIDTH
        width = x
        span_days = (end - start).days + 1
        height = HEADER_HEIGHT + span_days * ROW_HEIGHT

        col_center = {c.key: c.x + c.width // 2 for c in columns}
        pack_left = {
            i: LABEL_WIDTH + (YARD_LANE_WIDTH if yard else 0) + i * JOB_LANE_WIDTH
            for i in range(pack_count)
        }

        def day_top(d: date) -> int:
            d = max(start, min(end, d))
            return HEADER_HEIGHT + (d - start).days * ROW_HEIGHT

        def load_meta(load: Load) -> dict[str, str]:
            m = load.movement
            haulier = "—"
            if load.lorry is not None and load.lorry.haulier is not None:
                haulier = load.lorry.haulier.name
            return {
                "origin_name": m.origin.name,
                "dest_name": m.destination.name,
                "depart_label": m.depart_after.astimezone(timezone).strftime("%d %b %Y %H:%M"),
                "arrive_label": m.arrive_by.astimezone(timezone).strftime("%d %b %Y %H:%M"),
                "vehicle_type": load.lorry_type.name if load.lorry_type else "",
                "haulier_name": haulier,
            }

        def job_for_arrival(load: Load) -> Job | None:
            m = load.movement
            candidates: list[tuple[timedelta, Job]] = []
            for job in jobs:
                if job.location_id != m.destination_location_id:
                    continue
                w0, w1 = job_windows[job.id]
                if w0 - timedelta(days=3) <= m.arrive_by <= w1 + timedelta(days=1):
                    return job
                candidates.append((abs(m.arrive_by - w0), job))
            if not candidates:
                return None
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]

        def job_for_departure(load: Load) -> Job | None:
            m = load.movement
            in_window: list[Job] = []
            finished_before: list[tuple[datetime, Job]] = []
            for job in jobs:
                if job.location_id != m.origin_location_id:
                    continue
                w0, w1 = job_windows[job.id]
                if w0 <= m.depart_after <= w1:
                    in_window.append(job)
                elif m.depart_after > w1:
                    finished_before.append((w1, job))
            if in_window:
                return max(in_window, key=lambda j: job_windows[j.id][1])
            if finished_before:
                finished_before.sort(key=lambda item: item[0], reverse=True)
                return finished_before[0][1]
            return None

        all_loads = [load for mov in movements for load in mov.loads]

        events_by_job: dict[int, list[FlowLoadEvent]] = defaultdict(list)
        # Collect raw yard marks / edges then group into convoys
        raw_yard: list[dict] = []
        raw_edges: list[dict] = []

        for load in all_loads:
            m = load.movement
            labels = _item_labels(load)
            content = ", ".join(labels) if labels else "(empty)"
            full = _expand_load_contents(load, links_by_parent)
            meta = load_meta(load)
            color = _color_index(load.load_number)
            href = f"/loads/{load.id}"
            depart_day = m.depart_after.astimezone(timezone).date()
            arrive_day = m.arrive_by.astimezone(timezone).date()

            dest_job = job_for_arrival(load)
            origin_job = job_for_departure(load)

            if dest_job is not None:
                w0, _w1 = job_windows[dest_job.id]
                block_start = w0.astimezone(timezone).date()
                show_arrive = arrive_day if arrive_day >= block_start else block_start
                if start <= show_arrive <= end:
                    off = (show_arrive - block_start).days
                    if off >= 0:
                        events_by_job[dest_job.id].append(
                            FlowLoadEvent(
                                off,
                                "arrival",
                                f"L{load.load_number} {content}",
                                href,
                                load.id,
                                load.load_number,
                                color,
                                " ".join(labels),
                                f"L{load.load_number} {content} {dest_job.job_code}",
                                full,
                                **meta,
                            )
                        )

            if origin_job is not None:
                w0, w1 = job_windows[origin_job.id]
                block_start = w0.astimezone(timezone).date()
                block_end = _last_day(w1.astimezone(timezone))
                show_day = depart_day if depart_day <= block_end else block_end
                if start <= show_day <= end:
                    off = (show_day - block_start).days
                    if off >= 0:
                        events_by_job[origin_job.id].append(
                            FlowLoadEvent(
                                off,
                                "departure",
                                f"L{load.load_number} {content}",
                                href,
                                load.id,
                                load.load_number,
                                color,
                                " ".join(labels),
                                f"L{load.load_number} {content} {origin_job.job_code}",
                                full,
                                **meta,
                            )
                        )

            if yard is not None:
                if m.origin_location_id == yard.id and start <= depart_day <= end:
                    raw_yard.append(
                        {
                            "day": depart_day,
                            "kind": "yard_out",
                            "load": load,
                            "labels": labels,
                            "content": content,
                            "full": full,
                            "meta": meta,
                            "href": href,
                            "color": color,
                        }
                    )
                if m.destination_location_id == yard.id and start <= arrive_day <= end:
                    raw_yard.append(
                        {
                            "day": arrive_day,
                            "kind": "yard_in",
                            "load": load,
                            "labels": labels,
                            "content": content,
                            "full": full,
                            "meta": meta,
                            "href": href,
                            "color": color,
                        }
                    )

            origin_key = dest_key = None
            if yard and m.origin_location_id == yard.id:
                origin_key = "yard"
            if yard and m.destination_location_id == yard.id:
                dest_key = "yard"
            if origin_job is not None:
                origin_key = f"pack-{packed[origin_job.id]}"
            if dest_job is not None:
                dest_key = f"pack-{packed[dest_job.id]}"
            if origin_key is None:
                for job in jobs:
                    if job.location_id == m.origin_location_id:
                        origin_key = f"pack-{packed[job.id]}"
                        break
            if dest_key is None:
                for job in jobs:
                    if job.location_id == m.destination_location_id:
                        dest_key = f"pack-{packed[job.id]}"
                        break

            if origin_key and dest_key and origin_key in col_center and dest_key in col_center:
                d0 = depart_day
                if origin_job is not None:
                    _w0, w1 = job_windows[origin_job.id]
                    block_end = _last_day(w1.astimezone(timezone))
                    if d0 > block_end:
                        d0 = block_end
                d1 = arrive_day
                if dest_job is not None:
                    w0, _w1 = job_windows[dest_job.id]
                    block_start = w0.astimezone(timezone).date()
                    if d1 < block_start:
                        d1 = block_start
                d0 = max(start, min(end, d0))
                d1 = max(start, min(end, d1))
                # Skip only true zero-length self-loops (same cell)
                if origin_key == dest_key and d0 == d1:
                    continue
                x1 = col_center[origin_key]
                x2 = col_center[dest_key]
                if origin_key == dest_key:
                    # Same pack lane: nudge right so the arrow is visible beside the blocks
                    x1 = x2 = col_center[origin_key] + JOB_LANE_WIDTH // 3
                y1 = day_top(d0) + ROW_HEIGHT - 6
                y2 = day_top(d1) + 8
                raw_edges.append(
                    {
                        "origin_key": origin_key,
                        "dest_key": dest_key,
                        "d0": d0,
                        "d1": d1,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "load": load,
                        "full": full,
                        "meta": meta,
                        "href": href,
                        "color": color,
                    }
                )

        # Group yard marks by day + direction into one call-out
        yard_marks: list[FlowYardMark] = []
        yard_groups: dict[tuple[date, str], list[dict]] = defaultdict(list)
        for item in raw_yard:
            yard_groups[(item["day"], item["kind"])].append(item)
        for (day, kind), items in sorted(yard_groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            items.sort(key=lambda i: i["load"].load_number)
            numbers = [i["load"].load_number for i in items]
            ids = [i["load"].id for i in items]
            label = _format_load_list(numbers)
            prefix = "out" if kind == "yard_out" else "in"
            contents = " · ".join(
                f"L{i['load'].load_number}: {i['content']}" for i in items
            )
            dests = sorted({i["meta"]["dest_name"] for i in items})
            origins = sorted({i["meta"]["origin_name"] for i in items})
            first = items[0]
            yard_marks.append(
                FlowYardMark(
                    day,
                    day_top(day),
                    kind,
                    f"{prefix} {label}",
                    first["href"],
                    tuple(ids),
                    tuple(numbers),
                    first["color"],
                    " ".join(f"L{n}" for n in numbers),
                    f"{prefix} {label} {contents}",
                    contents,
                    origins[0] if len(origins) == 1 else ", ".join(origins),
                    dests[0] if len(dests) == 1 else ", ".join(dests),
                    first["meta"]["depart_label"]
                    if len(items) == 1
                    else f"{items[0]['meta']['depart_label']} (+{len(items) - 1})",
                    first["meta"]["arrive_label"]
                    if len(items) == 1
                    else f"{items[0]['meta']['arrive_label']} (+{len(items) - 1})",
                    first["meta"]["vehicle_type"] if len(items) == 1 else f"{len(items)} loads",
                    first["meta"]["haulier_name"] if len(items) == 1 else "—",
                )
            )

        # Group edges that share the same corridor + displayed days into one multi-label arrow
        edges: list[FlowEdge] = []
        edge_groups: dict[tuple, list[dict]] = defaultdict(list)
        for item in raw_edges:
            key = (item["origin_key"], item["dest_key"], item["d0"], item["d1"])
            edge_groups[key].append(item)
        for key, items in edge_groups.items():
            items.sort(key=lambda i: i["load"].load_number)
            numbers = [i["load"].load_number for i in items]
            ids = [i["load"].id for i in items]
            label = _format_load_list(numbers)
            first = items[0]
            contents = " · ".join(
                f"L{i['load'].load_number}: {i['full']}" for i in items
            )
            x1, y1, x2, y2 = first["x1"], first["y1"], first["x2"], first["y2"]
            lx = (x1 + x2) // 2
            ly = (y1 + y2) // 2
            lw = _label_width_px(label)
            edges.append(
                FlowEdge(
                    tuple(ids),
                    tuple(numbers),
                    label,
                    first["href"],
                    first["color"],
                    x1,
                    y1,
                    x2,
                    y2,
                    lx,
                    ly,
                    lw,
                    contents,
                    first["meta"]["origin_name"],
                    first["meta"]["dest_name"],
                    first["meta"]["depart_label"]
                    if len(items) == 1
                    else f"{items[0]['meta']['depart_label']} · {len(items)} loads",
                    first["meta"]["arrive_label"]
                    if len(items) == 1
                    else f"{items[0]['meta']['arrive_label']} · {len(items)} loads",
                    first["meta"]["vehicle_type"] if len(items) == 1 else f"{len(items)}× lorry",
                    first["meta"]["haulier_name"] if len(items) == 1 else "—",
                )
            )

        job_blocks: list[FlowJobBlock] = []
        for job in jobs:
            w0, w1 = job_windows[job.id]
            span_start = w0.astimezone(timezone).date()
            span_end = _last_day(w1.astimezone(timezone))
            vis_start = max(start, span_start)
            vis_end = min(end, span_end)
            if vis_start > vis_end:
                continue
            pack_i = packed[job.id]
            left = pack_left[pack_i]
            top = day_top(vis_start)
            n_days = (vis_end - vis_start).days + 1

            # Up band relative to visible block
            up_offset = 0
            up_height = 0
            up_win = _up_window(job)
            if up_win is not None:
                up0, up1 = up_win
                band_start = max(vis_start, up0)
                band_end = min(vis_end, up1)
                if band_start <= band_end:
                    up_offset = (band_start - vis_start).days * ROW_HEIGHT
                    up_height = ((band_end - band_start).days + 1) * ROW_HEIGHT

            base_off = (vis_start - span_start).days
            raw_events: list[FlowLoadEvent] = []
            for ev in events_by_job.get(job.id, ()):
                vis_off = ev.day_offset - base_off
                if 0 <= vis_off < n_days:
                    raw_events.append(
                        FlowLoadEvent(
                            vis_off,
                            ev.kind,
                            ev.text,
                            ev.href,
                            ev.load_id,
                            ev.load_number,
                            ev.color_index,
                            ev.codes,
                            ev.search,
                            ev.full_contents,
                            ev.origin_name,
                            ev.dest_name,
                            ev.depart_label,
                            ev.arrive_label,
                            ev.vehicle_type,
                            ev.haulier_name,
                        )
                    )
            raw_events.sort(key=lambda e: (e.day_offset, e.kind, e.load_number))
            stack_counters: dict[tuple[int, str], int] = defaultdict(int)
            events: list[FlowLoadEvent] = []
            for ev in raw_events:
                key = (ev.day_offset, ev.kind)
                stack = stack_counters[key]
                stack_counters[key] = stack + 1
                events.append(
                    FlowLoadEvent(
                        ev.day_offset,
                        ev.kind,
                        ev.text,
                        ev.href,
                        ev.load_id,
                        ev.load_number,
                        ev.color_index,
                        ev.codes,
                        ev.search,
                        ev.full_contents,
                        ev.origin_name,
                        ev.dest_name,
                        ev.depart_label,
                        ev.arrive_label,
                        ev.vehicle_type,
                        ev.haulier_name,
                        stack,
                    )
                )
            job_blocks.append(
                FlowJobBlock(
                    job.id,
                    job.job_code,
                    _tent_summary(job),
                    job.commercial_status.value,
                    f"/jobs/{job.id}",
                    pack_i,
                    left + 2,
                    top,
                    JOB_LANE_WIDTH - 4,
                    n_days * ROW_HEIGHT,
                    n_days,
                    tuple(events),
                    up_offset,
                    up_height,
                )
            )

        days = [
            FlowDay(start + timedelta(days=i), HEADER_HEIGHT + i * ROW_HEIGHT)
            for i in range(span_days)
        ]

        yard_stock = self._yard_stock_by_day(
            yard, all_loads, start, end, timezone
        )

        return FlowData(
            start,
            end,
            LABEL_WIDTH,
            HEADER_HEIGHT,
            ROW_HEIGHT,
            JOB_HEAD_HEIGHT,
            width,
            height,
            columns,
            days,
            job_blocks,
            yard_marks,
            edges,
            yard_stock,
        )

    def _yard_stock_by_day(
        self,
        yard: Location | None,
        loads: list[Load],
        start: date,
        end: date,
        timezone: ZoneInfo,
    ) -> dict[str, dict[str, object]]:
        if yard is None:
            return {}
        assets = self.session.scalars(
            select(EquipmentAsset).options(selectinload(EquipmentAsset.equipment_type))
        ).all()
        asset_location: dict[int, int | None] = {
            a.id: a.initial_location_id for a in assets
        }
        asset_code = {a.id: a.asset_code for a in assets}
        qty_stock: dict[str, int] = defaultdict(int)
        for load in loads:
            if load.movement.origin_location_id != yard.id:
                continue
            for item in load.items:
                if item.equipment_asset_id is None:
                    qty_stock[item.resolved_type.code] += int(item.quantity)

        events: list[tuple[date, int, str, Load]] = []
        for load in loads:
            m = load.movement
            events.append((m.depart_after.astimezone(timezone).date(), 1, "depart", load))
            events.append((m.arrive_by.astimezone(timezone).date(), 0, "arrive", load))
        events.sort(key=lambda e: (e[0], e[1]))

        def apply_event(kind: str, load: Load) -> None:
            m = load.movement
            for item in load.items:
                if item.equipment_asset_id is not None:
                    aid = item.equipment_asset_id
                    if kind == "depart" and asset_location.get(aid) == m.origin_location_id:
                        asset_location[aid] = m.destination_location_id
                    elif kind == "arrive" and m.destination_location_id == yard.id:
                        asset_location[aid] = yard.id
                    continue
                code = item.resolved_type.code
                qty = int(item.quantity)
                if kind == "depart" and m.origin_location_id == yard.id:
                    qty_stock[code] = max(0, qty_stock.get(code, 0) - qty)
                elif kind == "arrive" and m.destination_location_id == yard.id:
                    qty_stock[code] = qty_stock.get(code, 0) + qty

        for d, _o, kind, load in events:
            if d < start:
                apply_event(kind, load)

        result: dict[str, dict[str, object]] = {}
        ei = 0
        while ei < len(events) and events[ei][0] < start:
            ei += 1
        day = start
        while day <= end:
            while ei < len(events) and events[ei][0] == day:
                apply_event(events[ei][2], events[ei][3])
                ei += 1
            assets_here = sorted(
                asset_code[aid] for aid, loc in asset_location.items() if loc == yard.id
            )
            quantities = sorted([[c, n] for c, n in qty_stock.items() if n > 0])
            bits = assets_here + [f"{c}×{n}" for c, n in quantities]
            result[day.isoformat()] = {
                "assets": assets_here,
                "quantities": quantities,
                "summary": ", ".join(bits) if bits else "(empty / not tracked)",
            }
            day += timedelta(days=1)
        return result
