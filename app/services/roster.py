from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models.administration import (
    CrewAvailability,
    CrewAvailabilityStatus,
    CrewAvailabilityWindow,
    CrewMember,
    TentmasterMembership,
)
from app.models.jobs import JobPhase


class RosterIndex:
    """Bounded snapshot of Tentmaster membership and crew availability for a datetime window.

    Build once per board/costing/conflict pass and reuse via `roster_for()`, which issues no
    further queries. Calling `roster_for_tentmaster()` inside a per-phase or per-day loop instead
    would reintroduce the N+1 pattern this class exists to avoid.
    """

    def __init__(
        self,
        memberships: list[TentmasterMembership],
        unavailable: dict[int, list[CrewAvailability]],
        available_windows: dict[int, list[CrewAvailabilityWindow]],
    ) -> None:
        self._memberships = memberships
        self._unavailable = unavailable
        self._available_windows = available_windows

    @classmethod
    def build(cls, session: Session, start_at: datetime, end_at: datetime) -> RosterIndex:
        tz = ZoneInfo(get_settings().default_timezone)
        start_date = start_at.astimezone(tz).date()
        end_date = end_at.astimezone(tz).date()
        memberships = list(
            session.scalars(
                select(TentmasterMembership)
                .where(
                    TentmasterMembership.start_at < end_date,
                    (TentmasterMembership.end_at.is_(None))
                    | (TentmasterMembership.end_at > start_date),
                )
                .options(selectinload(TentmasterMembership.crew_member))
            )
        )
        crew_member_ids = {membership.crew_member_id for membership in memberships}
        unavailable: dict[int, list[CrewAvailability]] = {}
        available_windows: dict[int, list[CrewAvailabilityWindow]] = {}
        if crew_member_ids:
            rows = session.scalars(
                select(CrewAvailability).where(
                    CrewAvailability.crew_member_id.in_(crew_member_ids),
                    CrewAvailability.status != CrewAvailabilityStatus.AVAILABLE_OVERRIDE,
                    CrewAvailability.start_at < end_date,
                    CrewAvailability.end_at >= start_date,
                )
            )
            for row in rows:
                unavailable.setdefault(row.crew_member_id, []).append(row)
            # No date filter here: a crew member with only out-of-range windows must still be
            # known to have *some* windows, so they are constrained rather than treated as always
            # available (see `_is_within_available_windows`).
            window_rows = session.scalars(
                select(CrewAvailabilityWindow).where(
                    CrewAvailabilityWindow.crew_member_id.in_(crew_member_ids)
                )
            )
            for window in window_rows:
                available_windows.setdefault(window.crew_member_id, []).append(window)
        return cls(memberships, unavailable, available_windows)

    def roster_for(
        self, tentmaster_id: int | None, start_at: datetime, end_at: datetime
    ) -> list[CrewMember]:
        """Crew members active on `tentmaster_id`'s roster at any point in [start_at, end_at)."""

        if tentmaster_id is None:
            return []
        tz = ZoneInfo(get_settings().default_timezone)
        members: list[CrewMember] = []
        seen: set[int] = set()
        for membership in self._memberships:
            if membership.tentmaster_id != tentmaster_id:
                continue
            if membership.crew_member_id in seen:
                continue
            member_start = datetime.combine(membership.start_at, time.min, tz)
            member_end = (
                datetime.combine(membership.end_at, time.min, tz)
                if membership.end_at is not None
                else None
            )
            if not (member_start < end_at and (member_end is None or member_end > start_at)):
                continue
            if self._is_unavailable(membership.crew_member_id, start_at, end_at, tz):
                continue
            if not self._is_within_available_windows(
                membership.crew_member_id, start_at, end_at, tz
            ):
                continue
            seen.add(membership.crew_member_id)
            members.append(membership.crew_member)
        return members

    def _is_unavailable(
        self, crew_member_id: int, start_at: datetime, end_at: datetime, tz: ZoneInfo
    ) -> bool:
        for row in self._unavailable.get(crew_member_id, ()):
            row_start = datetime.combine(row.start_at, time.min, tz)
            row_end = datetime.combine(row.end_at + timedelta(days=1), time.min, tz)
            if row_start < end_at and row_end > start_at:
                return True
        return False

    def _is_within_available_windows(
        self, crew_member_id: int, start_at: datetime, end_at: datetime, tz: ZoneInfo
    ) -> bool:
        """True if `crew_member_id` has no windows at all (always available), or if
        [start_at, end_at) overlaps at least one of their explicit available windows.
        """

        windows = self._available_windows.get(crew_member_id, ())
        if not windows:
            return True
        for window in windows:
            window_start = datetime.combine(window.start_at, time.min, tz)
            window_end = (
                datetime.combine(window.end_at + timedelta(days=1), time.min, tz)
                if window.end_at is not None
                else None
            )
            if window_start < end_at and (window_end is None or window_end > start_at):
                return True
        return False


def roster_for_tentmaster(
    session: Session, tentmaster_id: int, start_at: datetime, end_at: datetime
) -> list[CrewMember]:
    """One-shot convenience wrapper for single-phase call sites (not for use in a loop)."""

    return RosterIndex.build(session, start_at, end_at).roster_for(tentmaster_id, start_at, end_at)


@dataclass(frozen=True)
class PhaseRoster:
    """A phase's crew: derived Tentmaster members plus any local crew booked over dates that
    overlap the phase (see `LocalCrewBooking`).

    Overlap-not-containment: a member (or a local-crew booking) counts toward the whole phase if
    it overlaps any part of it, matching the coarseness the previous row-per-person model already
    had.
    """

    required: int
    members: tuple[CrewMember, ...]
    local_crew: int = 0

    @property
    def assigned(self) -> int:
        return len(self.members) + self.local_crew

    @property
    def shortfall(self) -> int:
        return max(0, self.required - self.assigned)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(member.name for member in self.members)


def phase_roster(phase: JobPhase, index: RosterIndex) -> PhaseRoster:
    """Combine `index`'s derived Tentmaster roster with `phase.job.local_crew_bookings` that
    overlap this phase's dates. Requires `phase.job.local_crew_bookings` to already be loaded —
    issues zero additional queries itself.
    """

    derived = tuple(index.roster_for(phase.tentmaster_id, phase.start_at, phase.end_at))
    local_crew = sum(
        booking.headcount
        for booking in phase.job.local_crew_bookings
        if booking.start_at < phase.end_at and booking.end_at > phase.start_at
    )
    return PhaseRoster(phase.required_headcount, derived, local_crew)
