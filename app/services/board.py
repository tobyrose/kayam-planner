from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models.administration import EquipmentAsset, Tentmaster
from app.models.crew_movements import CrewMovement
from app.models.crew_planning import CrewActivity
from app.models.jobs import (
    Job,
    JobEquipmentRequirement,
    JobPhase,
    JobTentRequirement,
    JobTentSection,
    PhaseType,
)
from app.models.logistics import EquipmentMovement, Load, LoadItem
from app.services.jobs import BREAK_TRAIL_DAYS, BUILD_LEAD_DAYS
from app.services.roster import RosterIndex, phase_roster
from app.services.section_coverage import (
    format_section_shortfall,
    job_has_section_shortfall,
    section_shortfalls,
)


@dataclass(frozen=True)
class BoardBlock:
    kind: str
    record_id: int
    label: str
    subtitle: str
    href: str
    status: str
    job_id: int | None = None
    phase_id: int | None = None
    conflict: bool = False
    segment: str = "solo"
    # Extra stacked lines rendered under the subtitle: load arrive/depart, crew-move references,
    # local-crew arrive/depart, contract Up/Down markers — auto-growing the block vertically
    # rather than living in their own side columns (D0xx).
    detail_lines: tuple[str, ...] = ()
    # Phase type value (build/up/break/…) for colour coding; empty for non-job blocks.
    phase_type: str = ""


@dataclass(frozen=True)
class BoardDay:
    day: date
    tentmasters: dict[int, list[BoardBlock]]
    # Column index -> blocks. A job keeps the same column for the whole span of its currently
    # unassigned phases (interval-packed once for the whole board, not per day), so it doesn't
    # jump columns from one day to the next.
    unassigned: dict[int, list[BoardBlock]]


@dataclass(frozen=True)
class BoardData:
    start: date
    end: date
    tentmasters: list[tuple[int, str]]
    unassigned_columns: int
    days: list[BoardDay]

    def jsonable(self) -> dict[str, object]:
        return asdict(self)


def _overlaps_day(start: datetime, end: datetime, day: date) -> bool:
    timezone = ZoneInfo(get_settings().default_timezone)
    day_start = datetime.combine(day, time.min, timezone)
    day_end = day_start + timedelta(days=1)
    return start < day_end and end > day_start


def _last_day(end_at: datetime) -> date:
    """Last calendar day a half-open [start, end) span actually touches."""
    return (end_at - timedelta(microseconds=1)).date()


def _segment(day: date, span_start: date, span_end: date) -> str:
    """Where `day` sits within a multi-day span, so adjacent-day blocks can be
    rendered as one continuous bar instead of repeated per-day flags."""
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


def _job_window(job: Job) -> tuple[datetime, datetime] | None:
    """The outer bound the job's equipment/crew activity spans: earliest tent's Build start to
    latest tent's Break end. None if the job has no tents yet."""
    if not job.tent_requirements:
        return None
    starts = [
        requirement.contracted_up_at - timedelta(days=BUILD_LEAD_DAYS)
        for requirement in job.tent_requirements
    ]
    ends = [
        requirement.contracted_down_at + timedelta(days=BREAK_TRAIL_DAYS)
        for requirement in job.tent_requirements
    ]
    return min(starts), max(ends)


def _pack_unassigned_columns(
    spans: dict[int, tuple[datetime, datetime]],
) -> dict[int, int]:
    """Greedy interval-graph colouring: a job keeps the same column for the whole span of its
    unassigned phases, using as few concurrent columns as the range actually needs."""
    column_ends: list[datetime] = []
    assignment: dict[int, int] = {}
    for job_id, (start, end) in sorted(spans.items(), key=lambda item: item[1][0]):
        for index, column_end in enumerate(column_ends):
            if start >= column_end:
                column_ends[index] = end
                assignment[job_id] = index
                break
        else:
            column_ends.append(end)
            assignment[job_id] = len(column_ends) - 1
    return assignment


def _local_clock(value: datetime) -> str:
    """Contract times are stored UTC-aware; show them in the planner's default timezone."""
    timezone = ZoneInfo(get_settings().default_timezone)
    return value.astimezone(timezone).strftime("%H:%M")


def _phase_block_label(phase: JobPhase, *, day: date | None = None) -> str:
    """Job code · phase. Contract Up/Break times only when `day` is that contract day."""
    phase_word = phase.phase_type.value.replace("_", " ")
    timezone = ZoneInfo(get_settings().default_timezone)
    if phase.phase_type == PhaseType.UP:
        requirement = next(
            (
                tent
                for tent in phase.job.tent_requirements
                if tent.id == phase.job_tent_requirement_id
            ),
            None,
        )
        if requirement is not None:
            tent_label = requirement.custom_name or requirement.sequence_code
            up_day = requirement.contracted_up_at.astimezone(timezone).date()
            if day is None or day == up_day:
                return (
                    f"{phase.job.job_code} · up "
                    f"{_local_clock(requirement.contracted_up_at)} ({tent_label})"
                )
            return f"{phase.job.job_code} · up"
    if phase.phase_type == PhaseType.BREAK and phase.job.tent_requirements:
        tents = phase.job.tent_requirements
        if len(tents) == 1:
            tent = tents[0]
            down_day = tent.contracted_down_at.astimezone(timezone).date()
            if day is None or day == down_day:
                return (
                    f"{phase.job.job_code} · break {_local_clock(tent.contracted_down_at)}"
                )
            return f"{phase.job.job_code} · break"
    return f"{phase.job.job_code} · {phase_word}"


def _merged_up_label(up_phases: list[JobPhase]) -> str:
    """One label for one or many concurrent Up phases of the same job in the same column."""
    if len(up_phases) == 1:
        return _phase_block_label(up_phases[0])
    job = up_phases[0].job
    tent_bits: list[str] = []
    for phase in sorted(up_phases, key=lambda item: item.start_at):
        requirement = next(
            (
                tent
                for tent in job.tent_requirements
                if tent.id == phase.job_tent_requirement_id
            ),
            None,
        )
        if requirement is None:
            continue
        tent_bits.append(
            f"{_local_clock(requirement.contracted_up_at)} "
            f"({requirement.custom_name or requirement.sequence_code})"
        )
    if tent_bits:
        return f"{job.job_code} · up " + " · ".join(tent_bits)
    return f"{job.job_code} · up ({len(up_phases)} tents)"


def _ups_with_contract_up_on_day(up_phases: list[JobPhase], day: date) -> list[JobPhase]:
    """Up phases whose tent's contract Up wall-clock date is exactly this diary day."""
    timezone = ZoneInfo(get_settings().default_timezone)
    matching: list[JobPhase] = []
    for phase in up_phases:
        requirement = next(
            (
                tent
                for tent in phase.job.tent_requirements
                if tent.id == phase.job_tent_requirement_id
            ),
            None,
        )
        if requirement is None:
            continue
        if requirement.contracted_up_at.astimezone(timezone).date() == day:
            matching.append(phase)
    return matching


def _detail_lines(
    phase: JobPhase,
    day: date,
    loads_by_job: dict[int, list[Load]],
    crew_moves_by_tentmaster: dict[int, list[CrewMovement]],
    *,
    include_all_tents: bool = False,
) -> tuple[str, ...]:
    lines: list[str] = []
    for requirement in phase.job.tent_requirements:
        # An Up phase only annotates its own tent's milestones unless we are rendering a merged
        # multi-tent Up block (include_all_tents=True). Build/Break are always job-wide.
        if (
            not include_all_tents
            and phase.job_tent_requirement_id is not None
            and requirement.id != phase.job_tent_requirement_id
        ):
            continue
        label = requirement.custom_name or requirement.sequence_code
        timezone = ZoneInfo(get_settings().default_timezone)
        local_up = requirement.contracted_up_at.astimezone(timezone)
        local_down = requirement.contracted_down_at.astimezone(timezone)
        if local_up.date() == day:
            lines.append(f"UP {_local_clock(requirement.contracted_up_at)} ({label})")
        if local_down.date() == day:
            lines.append(f"BREAK {_local_clock(requirement.contracted_down_at)} ({label})")
    for booking in phase.job.local_crew_bookings:
        if booking.start_at.date() == day:
            lines.append(f"Local crew arrive: {booking.headcount}")
        if _last_day(booking.end_at) == day:
            lines.append(f"Local crew depart: {booking.headcount}")
    for load in loads_by_job.get(phase.job_id, []):
        movement = load.movement
        if _overlaps_day(movement.depart_after, movement.arrive_by, day):
            lines.append(
                f"Load {load.display_code}: {movement.origin.name} → {movement.destination.name}"
            )
    if phase.tentmaster_id is not None:
        for crew_movement in crew_moves_by_tentmaster.get(phase.tentmaster_id, []):
            if _overlaps_day(crew_movement.depart_after, crew_movement.arrive_by, day):
                lines.append(
                    f"Crew move {crew_movement.movement_code}: "
                    f"{crew_movement.origin.name} → {crew_movement.destination.name}"
                )
    return tuple(lines)


class BoardService:
    """Build the board with bounded collection queries, never one query per cell."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def build(self, start: date, end: date) -> BoardData:
        if end < start or (end - start).days > 370:
            raise ValueError("Board range must be ordered and no longer than 370 days")
        timezone = ZoneInfo(get_settings().default_timezone)
        range_start = datetime.combine(start, time.min, timezone)
        range_end = datetime.combine(end + timedelta(days=1), time.min, timezone)
        teams = self.session.scalars(
            select(Tentmaster).where(Tentmaster.active).order_by(Tentmaster.name)
        ).all()
        phases = self.session.scalars(
            select(JobPhase)
            .where(JobPhase.start_at < range_end, JobPhase.end_at > range_start)
            .options(
                selectinload(JobPhase.job).selectinload(Job.location),
                selectinload(JobPhase.job)
                .selectinload(Job.tent_requirements)
                .selectinload(JobTentRequirement.sections)
                .selectinload(JobTentSection.equipment_type),
                selectinload(JobPhase.job).selectinload(Job.local_crew_bookings),
                selectinload(JobPhase.job)
                .selectinload(Job.equipment_requirements)
                .selectinload(JobEquipmentRequirement.equipment_type),
            )
        ).all()
        activities = self.session.scalars(
            select(CrewActivity).where(
                CrewActivity.start_at < range_end, CrewActivity.end_at > range_start
            )
        ).all()
        loads = self.session.scalars(
            select(Load)
            .join(Load.movement)
            .where(
                EquipmentMovement.depart_after < range_end,
                EquipmentMovement.arrive_by > range_start,
            )
            .options(
                selectinload(Load.movement).selectinload(EquipmentMovement.origin),
                selectinload(Load.movement).selectinload(EquipmentMovement.destination),
                selectinload(Load.items)
                .selectinload(LoadItem.equipment_asset)
                .selectinload(EquipmentAsset.equipment_type),
                selectinload(Load.items).selectinload(LoadItem.equipment_type),
            )
        ).all()
        jobs = {phase.job_id: phase.job for phase in phases}
        tent_summaries = {job_id: _tent_summary(job) for job_id, job in jobs.items()}
        crew_moves = self.session.scalars(
            select(CrewMovement)
            .where(CrewMovement.depart_after < range_end, CrewMovement.arrive_by > range_start)
            .options(
                selectinload(CrewMovement.origin),
                selectinload(CrewMovement.destination),
            )
        ).all()
        roster_index = RosterIndex.build(self.session, range_start, range_end)

        loads_by_job: dict[int, list[Load]] = {}
        for load in loads:
            movement = load.movement
            # Match loads to jobs at the same destination whose operational window contains
            # the arrival (with a few days' lead for early staging before Build).
            job_id = next(
                (
                    job.id
                    for job in jobs.values()
                    if job.location_id == movement.destination_location_id
                    and (window := _job_window(job)) is not None
                    and window[0] - timedelta(days=3)
                    <= movement.arrive_by
                    <= window[1]
                ),
                None,
            )
            if job_id is not None:
                loads_by_job.setdefault(job_id, []).append(load)
        # Jobs whose required sections are not fully covered by loads to the site — same red
        # attention dot as crew shortfall on every phase block for that job.
        jobs_short_sections = {
            job_id
            for job_id, job in jobs.items()
            if job_has_section_shortfall(job, loads_by_job.get(job_id, []))
        }
        section_shortfall_lines = {
            job_id: format_section_shortfall(
                section_shortfalls(job, loads_by_job.get(job_id, []))
            )
            for job_id, job in jobs.items()
            if job_id in jobs_short_sections
        }
        crew_moves_by_tentmaster: dict[int, list[CrewMovement]] = {}
        for crew_movement in crew_moves:
            if crew_movement.tentmaster_id is not None:
                crew_moves_by_tentmaster.setdefault(crew_movement.tentmaster_id, []).append(
                    crew_movement
                )

        unassigned_phases = [phase for phase in phases if phase.tentmaster_id is None]
        unassigned_spans: dict[int, tuple[datetime, datetime]] = {}
        for phase in unassigned_phases:
            existing = unassigned_spans.get(phase.job_id)
            span_start = min(phase.start_at, existing[0]) if existing else phase.start_at
            span_end = max(phase.end_at, existing[1]) if existing else phase.end_at
            unassigned_spans[phase.job_id] = (span_start, span_end)
        unassigned_column_by_job = _pack_unassigned_columns(unassigned_spans)
        unassigned_columns = max(1, len(set(unassigned_column_by_job.values())))

        def _column_key(phase: JobPhase) -> tuple[str, int]:
            if phase.tentmaster_id is not None and phase.tentmaster_id in {
                team.id for team in teams
            }:
                return ("team", phase.tentmaster_id)
            return ("unassigned", unassigned_column_by_job[phase.job_id])

        # All Up phases for a job that share a column merge into one continuous bar (multi-tent
        # jobs like SOLIDAYS should not stack two Up cards once both tents are up).
        up_phases_by_group: dict[tuple[tuple[str, int], int], list[JobPhase]] = {}
        for phase in phases:
            if phase.phase_type != PhaseType.UP:
                continue
            up_phases_by_group.setdefault((_column_key(phase), phase.job_id), []).append(phase)

        days = []
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            team_blocks: dict[int, list[BoardBlock]] = {team.id: [] for team in teams}
            unassigned_blocks: dict[int, list[BoardBlock]] = {
                index: [] for index in range(unassigned_columns)
            }
            day_phases = [
                phase for phase in phases if _overlaps_day(phase.start_at, phase.end_at, day)
            ]
            # A Build->Up or Up->Break handover day doesn't need both cards in the same column —
            # the earlier phase's card is redundant once the later one has started there, and the
            # later one's own UP/BREAK detail line already says so. Scoped to (column, job): if
            # the later phase is assigned to a *different* Tentmaster (or still unassigned) than
            # the earlier one, the earlier phase's own column still needs its own card shown.
            phase_types_by_group: dict[tuple[tuple[str, int], int], set[PhaseType]] = {}
            for phase in day_phases:
                target = _column_key(phase)
                phase_types_by_group.setdefault((target, phase.job_id), set()).add(
                    phase.phase_type
                )

            emitted_up_groups: set[tuple[tuple[str, int], int]] = set()
            for phase in day_phases:
                target = _column_key(phase)
                group_key = (target, phase.job_id)
                types_present = phase_types_by_group[group_key]
                if phase.phase_type == PhaseType.BUILD and PhaseType.UP in types_present:
                    continue
                if phase.phase_type == PhaseType.UP and PhaseType.BREAK in types_present:
                    continue

                if phase.phase_type == PhaseType.UP:
                    if group_key in emitted_up_groups:
                        continue
                    emitted_up_groups.add(group_key)
                    group_ups = up_phases_by_group[group_key]
                    today_ups = [
                        item
                        for item in group_ups
                        if _overlaps_day(item.start_at, item.end_at, day)
                    ]
                    if not today_ups:
                        continue
                    span_start = min(item.start_at.date() for item in group_ups)
                    span_end = max(_last_day(item.end_at) for item in group_ups)
                    segment = _segment(day, span_start, span_end)
                    primary = min(today_ups, key=lambda item: (item.start_at, item.id))
                    roster = phase_roster(primary, roster_index)
                    # Combined crew when several Up phases share the column today.
                    if len(today_ups) > 1:
                        assigned = 0
                        required = 0
                        shortfall = False
                        for up_phase in today_ups:
                            up_roster = phase_roster(up_phase, roster_index)
                            assigned += up_roster.assigned
                            required += up_roster.required
                            shortfall = shortfall or up_roster.shortfall > 0
                        crew_text = f"{assigned}/{required} crew"
                        conflict = shortfall
                    else:
                        crew_text = f"{roster.assigned}/{roster.required} crew"
                        conflict = roster.shortfall > 0
                    conflict = conflict or primary.job_id in jobs_short_sections
                    subtitle_parts = [primary.job.location.name]
                    tent_summary = tent_summaries.get(primary.job_id)
                    if tent_summary:
                        subtitle_parts.append(tent_summary)
                    subtitle_parts.append(crew_text)
                    detail_lines = _detail_lines(
                        primary,
                        day,
                        loads_by_job,
                        crew_moves_by_tentmaster,
                        include_all_tents=len(group_ups) > 1,
                    )
                    short_line = section_shortfall_lines.get(primary.job_id)
                    if short_line and segment in ("start", "solo"):
                        detail_lines = (*detail_lines, short_line)
                    # Diary rule: contract Up clock/label only on the actual contracted Up day.
                    # Other Up days are a quiet continuous bar ("JOB · up"), no repeated UP time.
                    ups_going_up_today = _ups_with_contract_up_on_day(today_ups, day)
                    if ups_going_up_today:
                        label = (
                            _phase_block_label(ups_going_up_today[0])
                            if len(ups_going_up_today) == 1
                            else _merged_up_label(ups_going_up_today)
                        )
                    elif len(group_ups) > 1:
                        label = f"{primary.job.job_code} · up ({len(group_ups)} tents)"
                    else:
                        label = f"{primary.job.job_code} · up"
                    block = BoardBlock(
                        "job",
                        primary.id,
                        label,
                        " · ".join(subtitle_parts),
                        f"/jobs/{primary.job_id}",
                        primary.job.commercial_status.value,
                        job_id=primary.job_id,
                        phase_id=primary.id,
                        conflict=conflict,
                        segment=segment,
                        detail_lines=detail_lines,
                        phase_type=PhaseType.UP.value,
                    )
                else:
                    roster = phase_roster(phase, roster_index)
                    segment = _segment(day, phase.start_at.date(), _last_day(phase.end_at))
                    subtitle_parts = [phase.job.location.name]
                    tent_summary = tent_summaries.get(phase.job_id)
                    if tent_summary:
                        subtitle_parts.append(tent_summary)
                    subtitle_parts.append(f"{roster.assigned}/{roster.required} crew")
                    detail_lines = _detail_lines(
                        phase, day, loads_by_job, crew_moves_by_tentmaster
                    )
                    short_line = section_shortfall_lines.get(phase.job_id)
                    if short_line and segment in ("start", "solo"):
                        detail_lines = (*detail_lines, short_line)
                    label = _phase_block_label(phase, day=day)
                    block = BoardBlock(
                        "job",
                        phase.id,
                        label,
                        " · ".join(subtitle_parts),
                        f"/jobs/{phase.job_id}",
                        phase.job.commercial_status.value,
                        job_id=phase.job_id,
                        phase_id=phase.id,
                        conflict=roster.shortfall > 0 or phase.job_id in jobs_short_sections,
                        segment=segment,
                        detail_lines=detail_lines,
                        phase_type=phase.phase_type.value,
                    )

                if target[0] == "team":
                    team_blocks[target[1]].append(block)
                else:
                    unassigned_blocks[target[1]].append(block)
            for activity in activities:
                if activity.tentmaster_id in team_blocks and _overlaps_day(
                    activity.start_at, activity.end_at, day
                ):
                    team_blocks[activity.tentmaster_id].append(
                        BoardBlock(
                            "activity",
                            activity.id,
                            activity.title,
                            activity.activity_type.value.replace("_", " "),
                            "/planning",
                            "confirmed",
                            segment=_segment(
                                day, activity.start_at.date(), _last_day(activity.end_at)
                            ),
                        )
                    )
            days.append(BoardDay(day, team_blocks, unassigned_blocks))
        return BoardData(
            start, end, [(team.id, team.name) for team in teams], unassigned_columns, days
        )
