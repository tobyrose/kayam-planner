from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.administration import Tentmaster
from app.models.crew_planning import CrewActivity
from app.models.jobs import Job, JobPhase
from app.schemas.crew_planning import CrewActivityData
from app.services.roster import PhaseRoster, RosterIndex, phase_roster


class CrewPlanningError(Exception):
    pass


@dataclass(frozen=True)
class PhaseHeadcount:
    required: int
    assigned: int
    shortfall: int
    names: tuple[str, ...]


def _to_headcount(roster: PhaseRoster) -> PhaseHeadcount:
    return PhaseHeadcount(roster.required, roster.assigned, roster.shortfall, roster.names)


class CrewPlanningService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_activity(self, payload: dict[str, Any]) -> CrewActivity:
        values = CrewActivityData.model_validate(payload).model_dump()
        activity = CrewActivity(**values)
        self.session.add(activity)
        self.session.commit()
        self.session.refresh(activity)
        return activity

    def phase_headcount(
        self, phase: JobPhase, *, roster_index: RosterIndex | None = None
    ) -> PhaseHeadcount:
        index = roster_index or RosterIndex.build(self.session, phase.start_at, phase.end_at)
        return _to_headcount(phase_roster(phase, index))

    def daily_totals(self, start_date: date, end_date: date, timezone_name: str) -> dict[date, int]:
        totals = self.daily_totals_by_tentmaster(start_date, end_date, timezone_name)
        grand_totals: dict[date, int] = {}
        current = start_date
        while current <= end_date:
            grand_totals[current] = sum(totals[current].values())
            current += timedelta(days=1)
        return grand_totals

    def daily_totals_by_tentmaster(
        self, start_date: date, end_date: date, timezone_name: str
    ) -> dict[date, dict[int, int]]:
        tz = ZoneInfo(timezone_name)
        range_start = datetime.combine(start_date, time.min, tzinfo=tz)
        range_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
        teams = self.session.scalars(select(Tentmaster).where(Tentmaster.active)).all()
        phases = self.session.scalars(
            select(JobPhase)
            .where(JobPhase.start_at < range_end, JobPhase.end_at > range_start)
            .options(selectinload(JobPhase.job).selectinload(Job.local_crew_bookings))
        ).all()
        index = RosterIndex.build(self.session, range_start, range_end)
        totals: dict[date, dict[int, int]] = {}
        current = start_date
        while current <= end_date:
            day_start = datetime.combine(current, time.min, tzinfo=tz)
            day_end = day_start + timedelta(days=1)
            # Key 0 collects phases with no Tentmaster assigned yet, so the grand total (summed
            # in daily_totals()) still reflects local crew booked before that step.
            day_totals = {team.id: 0 for team in teams} | {0: 0}
            for phase in phases:
                if not (phase.start_at < day_end and phase.end_at > day_start):
                    continue
                key = phase.tentmaster_id if phase.tentmaster_id in day_totals else 0
                day_totals[key] += phase_roster(phase, index).assigned
            totals[current] = day_totals
            current += timedelta(days=1)
        return totals

