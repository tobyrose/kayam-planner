from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.administration import CrewAvailability, CrewAvailabilityStatus, Tentmaster
from app.models.crew_planning import CrewActivity, CrewAssignment
from app.models.jobs import CommercialStatus, JobPhase
from app.schemas.crew_planning import CrewActivityData, CrewAssignmentData


class CrewPlanningError(Exception):
    pass


class CrewHardConflictError(CrewPlanningError):
    pass


@dataclass(frozen=True)
class CrewConflict:
    severity: str
    message: str
    assignment_id: int | None = None


@dataclass(frozen=True)
class PhaseHeadcount:
    required: int
    assigned: int
    shortfall: int
    names: tuple[str, ...]


class CrewPlanningService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def assign(self, payload: dict[str, Any]) -> CrewAssignment:
        values = CrewAssignmentData.model_validate(payload).model_dump()
        phase = self.session.get(JobPhase, values["job_phase_id"])
        if phase is None:
            raise CrewPlanningError("Job phase not found")
        conflicts = self.check_assignment_conflicts(values)
        if phase.job.commercial_status == CommercialStatus.CONFIRMED and any(
            conflict.severity == "hard" for conflict in conflicts
        ):
            raise CrewHardConflictError("; ".join(conflict.message for conflict in conflicts))
        assignment = CrewAssignment(**values)
        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def create_activity(self, payload: dict[str, Any]) -> CrewActivity:
        values = CrewActivityData.model_validate(payload).model_dump()
        activity = CrewActivity(**values)
        self.session.add(activity)
        self.session.commit()
        self.session.refresh(activity)
        return activity

    def check_assignment_conflicts(
        self, values: dict[str, Any], *, exclude_id: int | None = None
    ) -> list[CrewConflict]:
        crew_member_id = values.get("crew_member_id")
        if crew_member_id is None:
            return []
        conflicts: list[CrewConflict] = []
        overlap_query = (
            select(CrewAssignment)
            .join(CrewAssignment.job_phase)
            .join(JobPhase.job)
            .where(
                CrewAssignment.crew_member_id == crew_member_id,
                CrewAssignment.start_at < values["end_at"],
                CrewAssignment.end_at > values["start_at"],
            )
        )
        if exclude_id is not None:
            overlap_query = overlap_query.where(CrewAssignment.id != exclude_id)
        for assignment in self.session.scalars(overlap_query):
            severity = (
                "hard"
                if assignment.job_phase.job.commercial_status == CommercialStatus.CONFIRMED
                else "conditional"
            )
            conflicts.append(
                CrewConflict(
                    severity,
                    f"Overlaps {assignment.job_phase.job.name} "
                    f"({assignment.job_phase.phase_type.value})",
                    assignment.id,
                )
            )
        start_date = values["start_at"].date()
        end_date = values["end_at"].date()
        unavailable = self.session.scalars(
            select(CrewAvailability).where(
                CrewAvailability.crew_member_id == crew_member_id,
                CrewAvailability.start_at <= end_date,
                CrewAvailability.end_at >= start_date,
                CrewAvailability.status != CrewAvailabilityStatus.AVAILABLE_OVERRIDE,
            )
        ).all()
        conflicts.extend(
            CrewConflict("hard", f"Crew member is {item.status.value} in this period")
            for item in unavailable
        )
        return conflicts

    def phase_headcount(self, phase: JobPhase) -> PhaseHeadcount:
        names = tuple(
            assignment.crew_member.name
            if assignment.crew_member is not None
            else assignment.placeholder_name or "Placeholder"
            for assignment in phase.crew_assignments
        )
        assigned = len(names) + phase.job.local_crew_supplied
        required = phase.required_headcount + phase.job.local_crew_required
        return PhaseHeadcount(required, assigned, max(0, required - assigned), names)

    def daily_totals(self, start_date: date, end_date: date, timezone_name: str) -> dict[date, int]:
        tz = ZoneInfo(timezone_name)
        start_at = datetime.combine(start_date, time.min, tzinfo=tz)
        end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
        rows = self.session.execute(
            select(CrewAssignment.start_at, CrewAssignment.end_at, CrewAssignment.id).where(
                CrewAssignment.start_at < end_at,
                CrewAssignment.end_at > start_at,
            )
        ).all()
        totals: dict[date, int] = {}
        current = start_date
        while current <= end_date:
            day_start = datetime.combine(current, time.min, tzinfo=tz)
            day_end = day_start + timedelta(days=1)
            totals[current] = sum(
                1 for start, end, _ in rows if start < day_end and end > day_start
            )
            current += timedelta(days=1)
        return totals

    def board_data(self, start_date: date, end_date: date) -> dict[str, Any]:
        tentmasters = self.session.scalars(
            select(Tentmaster).where(Tentmaster.active).order_by(Tentmaster.name)
        ).all()
        phases = self.session.scalars(
            select(JobPhase)
            .join(JobPhase.job)
            .where(
                func.date(JobPhase.start_at) <= end_date.isoformat(),
                func.date(JobPhase.end_at) >= start_date.isoformat(),
            )
            .order_by(JobPhase.start_at)
        ).all()
        activities = self.session.scalars(
            select(CrewActivity).where(
                func.date(CrewActivity.start_at) <= end_date.isoformat(),
                func.date(CrewActivity.end_at) >= start_date.isoformat(),
            )
        ).all()
        days = []
        current = start_date
        while current <= end_date:
            day_phases = [
                phase for phase in phases if phase.start_at.date() <= current <= phase.end_at.date()
            ]
            day_activities = [
                activity
                for activity in activities
                if activity.start_at.date() <= current <= activity.end_at.date()
            ]
            days.append({"date": current, "phases": day_phases, "activities": day_activities})
            current += timedelta(days=1)
        return {"tentmasters": tentmasters, "days": days}
