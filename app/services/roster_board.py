from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models.administration import (
    CrewAvailabilityWindow,
    CrewMember,
    Tentmaster,
    TentmasterMembership,
)
from app.models.crew_planning import CrewActivity
from app.models.jobs import JobPhase
from app.services.administration import AdministrationService, MembershipOverlapError
from app.services.administration_catalog import ENTITY_BY_SLUG


class RosterBoardError(Exception):
    pass


def _add_shading_label(shading: dict[int, str], tentmaster_id: int, label: str) -> None:
    if tentmaster_id not in shading:
        return
    existing = shading[tentmaster_id]
    if not existing:
        shading[tentmaster_id] = label
    elif label not in existing.split(" + "):
        shading[tentmaster_id] = f"{existing} + {label}"


@dataclass(frozen=True)
class RosterMember:
    member: CrewMember
    available: bool


@dataclass(frozen=True)
class RosterDay:
    date: date
    members_by_tentmaster: dict[int, list[RosterMember]]
    unassigned: list[CrewMember]
    # Job codes and/or activity titles a Tentmaster is booked on that day (" + "-joined),
    # not just jobs — drives the amber cell shading in the template.
    shading_by_tentmaster: dict[int, str]


@dataclass(frozen=True)
class RosterBoardData:
    start: date
    end: date
    tentmasters: list[Tentmaster]
    days: list[RosterDay]


class RosterBoardService:
    """A roster-over-time view of who belongs to which Tentmaster, mirroring the crew board's
    date-vertical/team-column layout. Moving someone between teams here starts and ends
    `TentmasterMembership` rows directly, instead of that timeline being re-derived per job.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def build(self, start: date, end: date) -> RosterBoardData:
        if end < start or (end - start).days > 370:
            raise RosterBoardError(
                "Roster board range must be ordered and no longer than 370 days"
            )
        teams = self.session.scalars(
            select(Tentmaster).where(Tentmaster.active).order_by(Tentmaster.name)
        ).all()
        memberships = self.session.scalars(
            select(TentmasterMembership)
            .where(
                TentmasterMembership.start_at <= end,
                (TentmasterMembership.end_at.is_(None)) | (TentmasterMembership.end_at > start),
            )
            .options(selectinload(TentmasterMembership.crew_member))
        ).all()
        crew_members = self.session.scalars(
            select(CrewMember).where(CrewMember.active).order_by(CrewMember.name)
        ).all()
        timezone = ZoneInfo(get_settings().default_timezone)
        range_start = datetime.combine(start, time.min, timezone)
        range_end = datetime.combine(end + timedelta(days=1), time.min, timezone)
        phases = self.session.scalars(
            select(JobPhase)
            .where(
                JobPhase.tentmaster_id.is_not(None),
                JobPhase.start_at < range_end,
                JobPhase.end_at > range_start,
            )
            .options(selectinload(JobPhase.job))
        ).all()
        activities = self.session.scalars(
            select(CrewActivity).where(
                CrewActivity.tentmaster_id.is_not(None),
                CrewActivity.start_at < range_end,
                CrewActivity.end_at > range_start,
            )
        ).all()
        windows_by_member: dict[int, list[CrewAvailabilityWindow]] = {}
        for window in self.session.scalars(select(CrewAvailabilityWindow)):
            windows_by_member.setdefault(window.crew_member_id, []).append(window)

        def is_available(member_id: int, day: date) -> bool:
            windows = windows_by_member.get(member_id)
            if not windows:
                return True
            return any(
                window.start_at <= day and (window.end_at is None or window.end_at >= day)
                for window in windows
            )

        days = []
        current = start
        while current <= end:
            day_start = datetime.combine(current, time.min, timezone)
            day_end = day_start + timedelta(days=1)
            by_team: dict[int, list[RosterMember]] = {team.id: [] for team in teams}
            active_ids: set[int] = set()
            for membership in memberships:
                active = membership.start_at <= current and (
                    membership.end_at is None or membership.end_at > current
                )
                if not active:
                    continue
                active_ids.add(membership.crew_member_id)
                if membership.tentmaster_id in by_team:
                    available = is_available(membership.crew_member_id, current)
                    by_team[membership.tentmaster_id].append(
                        RosterMember(membership.crew_member, available)
                    )
            unassigned = [
                member
                for member in crew_members
                if member.id not in active_ids and is_available(member.id, current)
            ]
            jobs_by_team: dict[int, str] = {team.id: "" for team in teams}
            for phase in phases:
                if phase.start_at >= day_end or phase.end_at <= day_start:
                    continue
                assert phase.tentmaster_id is not None
                _add_shading_label(jobs_by_team, phase.tentmaster_id, phase.job.job_code)
            for activity in activities:
                if activity.start_at >= day_end or activity.end_at <= day_start:
                    continue
                assert activity.tentmaster_id is not None
                _add_shading_label(jobs_by_team, activity.tentmaster_id, activity.title)
            days.append(RosterDay(current, by_team, unassigned, jobs_by_team))
            current += timedelta(days=1)
        return RosterBoardData(start, end, list(teams), days)

    def move_crew_member(
        self, crew_member_id: int, to_tentmaster_id: int | None, effective_date: date
    ) -> None:
        """Reassign a crew member's Tentmaster membership from `effective_date` onward.

        Assigning to a new Tentmaster only replaces the timeline up to whatever's already
        scheduled next for this person — a future membership that already starts after
        `effective_date` resumes automatically once the new segment ends, rather than being
        silently overwritten or (the bug this replaced) treated as a false conflict just because
        it exists. Moving to Unassigned is the one genuinely open-ended action: since
        "unassigned" has no natural resume point, it clears every already-scheduled future
        segment too, not just the one active today.
        """

        crew_member = self.session.get(CrewMember, crew_member_id)
        if crew_member is None:
            raise RosterBoardError("Crew member not found")
        if to_tentmaster_id is not None and self.session.get(Tentmaster, to_tentmaster_id) is None:
            raise RosterBoardError("Tentmaster not found")

        current = self.session.scalar(
            select(TentmasterMembership).where(
                TentmasterMembership.crew_member_id == crew_member_id,
                TentmasterMembership.start_at <= effective_date,
                (TentmasterMembership.end_at.is_(None))
                | (TentmasterMembership.end_at > effective_date),
            )
        )
        future_segments = list(
            self.session.scalars(
                select(TentmasterMembership)
                .where(
                    TentmasterMembership.crew_member_id == crew_member_id,
                    TentmasterMembership.start_at > effective_date,
                )
                .order_by(TentmasterMembership.start_at)
            )
        )

        if current is not None and current.tentmaster_id == to_tentmaster_id:
            raise RosterBoardError("Crew member is already on that team on this date")
        if current is None and to_tentmaster_id is None and not future_segments:
            raise RosterBoardError("Crew member is already unassigned on this date")

        new_end_at = (
            future_segments[0].start_at
            if to_tentmaster_id is not None and future_segments
            else None
        )

        if to_tentmaster_id is not None:
            administration = AdministrationService(self.session)
            definition = ENTITY_BY_SLUG["tentmaster-memberships"]
            new_values = {
                "tentmaster_id": to_tentmaster_id,
                "crew_member_id": crew_member_id,
                "start_at": effective_date,
                "end_at": new_end_at,
                "is_default": True,
                "notes": None,
            }
            exclude_id = current.id if current is not None else None
            try:
                administration._validate_membership_overlap(  # noqa: SLF001
                    definition, new_values, exclude_id=exclude_id
                )
            except MembershipOverlapError:
                raise RosterBoardError(
                    "That move conflicts with an existing Tentmaster membership."
                ) from None
        else:
            for segment in future_segments:
                self.session.delete(segment)

        if current is not None:
            if current.start_at == effective_date:
                # This membership never took effect before today's second move — replace it
                # rather than shrinking it to a zero-length row, which the date_order
                # constraint rejects.
                self.session.delete(current)
            else:
                current.end_at = effective_date
        if to_tentmaster_id is not None:
            self.session.add(
                TentmasterMembership(
                    tentmaster_id=to_tentmaster_id,
                    crew_member_id=crew_member_id,
                    start_at=effective_date,
                    end_at=new_end_at,
                    is_default=True,
                )
            )
        self.session.commit()
