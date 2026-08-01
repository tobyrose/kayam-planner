from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models.administration import Tentmaster
from app.models.crew_movements import CrewMovement
from app.models.crew_planning import CrewActivity, CrewAssignment
from app.models.equipment_planning import AssignmentStatus, EquipmentAssignment
from app.models.jobs import Job, JobEquipmentRequirement, JobPhase
from app.models.logistics import EquipmentMovement, Load


@dataclass(frozen=True)
class BoardBlock:
    kind: str
    record_id: int
    label: str
    subtitle: str
    href: str
    status: str
    job_id: int | None = None
    asset_id: int | None = None
    asset_keys: str = ""
    load_id: int | None = None
    conflict: bool = False


@dataclass(frozen=True)
class BoardDay:
    day: date
    tentmasters: dict[int, list[BoardBlock]]
    operations: list[BoardBlock]
    logistics: list[BoardBlock]


@dataclass(frozen=True)
class BoardData:
    start: date
    end: date
    tentmasters: list[tuple[int, str]]
    days: list[BoardDay]

    def jsonable(self) -> dict[str, object]:
        return asdict(self)


def _overlaps_day(start: datetime, end: datetime, day: date) -> bool:
    timezone = ZoneInfo(get_settings().default_timezone)
    day_start = datetime.combine(day, time.min, timezone)
    day_end = day_start + timedelta(days=1)
    return start < day_end and end > day_start


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
                selectinload(JobPhase.crew_assignments).selectinload(CrewAssignment.crew_member),
            )
        ).all()
        activities = self.session.scalars(
            select(CrewActivity).where(
                CrewActivity.start_at < range_end, CrewActivity.end_at > range_start
            )
        ).all()
        equipment = self.session.scalars(
            select(EquipmentAssignment)
            .where(
                EquipmentAssignment.start_at < range_end,
                EquipmentAssignment.end_at > range_start,
                EquipmentAssignment.status == AssignmentStatus.ACTIVE,
            )
            .options(
                selectinload(EquipmentAssignment.equipment_asset),
                selectinload(EquipmentAssignment.requirement)
                .selectinload(JobEquipmentRequirement.job)
                .selectinload(Job.location),
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
                selectinload(Load.items),
            )
        ).all()
        jobs = {phase.job_id: phase.job for phase in phases}
        crew_moves = self.session.scalars(
            select(CrewMovement)
            .where(CrewMovement.depart_after < range_end, CrewMovement.arrive_by > range_start)
            .options(
                selectinload(CrewMovement.origin),
                selectinload(CrewMovement.destination),
            )
        ).all()

        days = []
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            team_blocks: dict[int, list[BoardBlock]] = {team.id: [] for team in teams}
            operations: list[BoardBlock] = []
            logistics: list[BoardBlock] = []
            for job in jobs.values():
                if job.must_be_up_at.date() == day:
                    operations.append(
                        BoardBlock(
                            "milestone",
                            job.id,
                            f"{job.job_code} · MUST BE UP",
                            job.location.name,
                            f"/jobs/{job.id}",
                            job.commercial_status.value,
                            job_id=job.id,
                        )
                    )
                if job.strike_available_at.date() == day:
                    operations.append(
                        BoardBlock(
                            "milestone",
                            job.id,
                            f"{job.job_code} · STRIKE",
                            job.location.name,
                            f"/jobs/{job.id}",
                            job.commercial_status.value,
                            job_id=job.id,
                        )
                    )
            for phase in phases:
                if not _overlaps_day(phase.start_at, phase.end_at, day):
                    continue
                assigned = len(phase.crew_assignments)
                block = BoardBlock(
                    "job",
                    phase.id,
                    f"{phase.job.job_code} · {phase.phase_type.value.replace('_', ' ')}",
                    f"{phase.job.location.name} · {assigned}/{phase.required_headcount} crew",
                    f"/jobs/{phase.job_id}",
                    phase.job.commercial_status.value,
                    job_id=phase.job_id,
                    conflict=assigned < phase.required_headcount,
                )
                if phase.tentmaster_id in team_blocks:
                    team_blocks[phase.tentmaster_id].append(block)
                operations.append(block)
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
                            "/planning/crew",
                            "confirmed",
                        )
                    )
            for assignment in equipment:
                if _overlaps_day(assignment.start_at, assignment.end_at, day):
                    job = assignment.requirement.job
                    operations.append(
                        BoardBlock(
                            "asset",
                            assignment.id,
                            assignment.equipment_asset.asset_code,
                            f"{job.job_code} · {job.location.name}",
                            f"/equipment/{assignment.equipment_asset_id}",
                            assignment.allocation_strength.value,
                            job_id=job.id,
                            asset_id=assignment.equipment_asset_id,
                        )
                    )
            for load in loads:
                movement = load.movement
                if _overlaps_day(movement.depart_after, movement.arrive_by, day):
                    yard = (
                        " · yard staging"
                        if (
                            movement.origin.location_type.value == "yard"
                            or movement.destination.location_type.value == "yard"
                        )
                        else ""
                    )
                    logistics.append(
                        BoardBlock(
                            "load",
                            load.id,
                            load.display_code,
                            f"{movement.origin.name} → {movement.destination.name}{yard}",
                            f"/loads/{load.id}",
                            load.status.value,
                            job_id=next(
                                (
                                    job.id
                                    for job in jobs.values()
                                    if job.location_id == movement.destination_location_id
                                    and job.site_access_at - timedelta(days=3)
                                    <= movement.arrive_by
                                    <= job.strike_available_at
                                ),
                                None,
                            ),
                            asset_keys=" ".join(
                                str(item.equipment_asset_id)
                                for item in load.items
                                if item.equipment_asset_id is not None
                            ),
                            load_id=load.id,
                        )
                    )
            for crew_movement in crew_moves:
                if _overlaps_day(crew_movement.depart_after, crew_movement.arrive_by, day):
                    logistics.append(
                        BoardBlock(
                            "crew-move",
                            crew_movement.id,
                            crew_movement.movement_code,
                            f"{crew_movement.origin.name} → {crew_movement.destination.name}",
                            f"/crew-moves/{crew_movement.id}",
                            crew_movement.status.value,
                        )
                    )
            days.append(BoardDay(day, team_blocks, operations, logistics))
        return BoardData(start, end, [(team.id, team.name) for team in teams], days)
