from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AwareDateTime, Base
from app.models.administration import (
    BuildStage,
    EquipmentType,
    Location,
    TentFamily,
    Tentmaster,
    utc_now,
)

if TYPE_CHECKING:
    from app.models.equipment_planning import EquipmentAssignment


class CommercialStatus(StrEnum):
    ENQUIRY = "enquiry"
    QUOTE_IN_PREPARATION = "quote_in_preparation"
    QUOTED = "quoted"
    DEPOSIT_REQUESTED = "deposit_requested"
    DEPOSIT_RECEIVED = "deposit_received"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class PlanningStatus(StrEnum):
    NOT_PLANNED = "not_planned"
    PROVISIONAL_PLAN = "provisional_plan"
    FEASIBLE = "feasible"
    AT_RISK = "at_risk"
    CONFLICT = "conflict"
    PLANNER_APPROVED = "planner_approved"
    OPERATIONALLY_LOCKED = "operationally_locked"


class RequirementSource(StrEnum):
    GENERATED = "generated"
    MANUAL = "manual"


class RequirementStatus(StrEnum):
    UNRESOLVED = "unresolved"
    PARTIALLY_ASSIGNED = "partially_assigned"
    ASSIGNED = "assigned"
    CONFLICT = "conflict"


class PhaseType(StrEnum):
    BUILD = "build"
    UP = "up"
    BREAK = "break"
    OTHER = "other"


class RecordSource(StrEnum):
    GENERATED = "generated"
    MANUAL = "manual"
    SUGGESTED = "suggested"


class Job(Base):
    """Contract Up/Down dates live per tent on `JobTentRequirement`, not here — a job with
    multiple tents can have different contract dates for each. `site_access_at`/`site_clear_by`
    are the only dates that genuinely apply to the whole job (general site availability)."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "confidence_percent IS NULL OR confidence_percent BETWEEN 0 AND 100",
            name="confidence_range",
        ),
        CheckConstraint("contract_revenue >= 0", name="contract_revenue_nonnegative"),
        CheckConstraint(
            "site_clear_by IS NULL OR site_access_at IS NULL OR site_clear_by >= site_access_at",
            name="clear_after_access",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    customer_name: Mapped[str] = mapped_column(String(200))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    commercial_status: Mapped[CommercialStatus] = mapped_column(
        Enum(CommercialStatus, native_enum=False, length=30),
        default=CommercialStatus.ENQUIRY,
        index=True,
    )
    planning_status: Mapped[PlanningStatus] = mapped_column(
        Enum(PlanningStatus, native_enum=False, length=30),
        default=PlanningStatus.NOT_PLANNED,
        index=True,
    )
    confidence_percent: Mapped[int | None] = mapped_column(Integer)
    contract_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    site_access_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), index=True)
    site_clear_by: Mapped[datetime | None] = mapped_column(AwareDateTime())
    maintenance_cover_required: Mapped[bool] = mapped_column(Boolean, default=False)
    catering_arrangement: Mapped[str | None] = mapped_column(Text)
    accommodation_arrangement: Mapped[str | None] = mapped_column(Text)
    ground_type: Mapped[str | None] = mapped_column(String(100))
    build_scope: Mapped[str | None] = mapped_column(Text)
    strike_scope: Mapped[str | None] = mapped_column(Text)
    operational_notes: Mapped[str | None] = mapped_column(Text)
    commercial_notes: Mapped[str | None] = mapped_column(Text)
    deposit_received_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    confirmed_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    cancelled_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=utc_now, onupdate=utc_now)

    location: Mapped[Location] = relationship()
    tent_requirements: Mapped[list[JobTentRequirement]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    equipment_requirements: Mapped[list[JobEquipmentRequirement]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    phases: Mapped[list[JobPhase]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    local_crew_bookings: Mapped[list[LocalCrewBooking]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def earliest_up_at(self) -> datetime | None:
        dates = [requirement.contracted_up_at for requirement in self.tent_requirements]
        return min(dates) if dates else None


class JobTentRequirement(Base):
    """A tent booked onto a job, described as an ordered sequence of section codes (see
    `JobTentSection`) rather than a named template — e.g. K-M-M-M-K, not "Kayam 10-pole". Poles
    and linked equipment are derived from the sequence, not stored here.

    `contracted_up_at`/`contracted_down_at` are this tent's fixed contract dates — set once when
    the tent is added, never edited afterwards (the "Up" `JobPhase` rows tied to this tent via
    `job_tent_requirement_id` are what's actually schedulable/reassignable, and must stay within
    this window). A job with multiple tents can have different contract dates per tent.
    """

    __tablename__ = "job_tent_requirements"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("contracted_down_at > contracted_up_at", name="contract_date_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    custom_name: Mapped[str | None] = mapped_column(String(200))
    contracted_up_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    contracted_down_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    job: Mapped[Job] = relationship(back_populates="tent_requirements")
    sections: Mapped[list[JobTentSection]] = relationship(
        back_populates="tent_requirement",
        cascade="all, delete-orphan",
        order_by="JobTentSection.sequence_index",
    )

    @property
    def sequence_code(self) -> str:
        return "".join(section.equipment_type.code for section in self.sections)

    @property
    def tent_family(self) -> TentFamily | None:
        return self.sections[0].equipment_type.tent_family if self.sections else None


class JobTentSection(Base):
    """One position in a `JobTentRequirement`'s section sequence (e.g. index 1 = 'M' in K-M-M-M-K).

    `equipment_type` must be a `category == "section"` type — enforced in `app/services/jobs.py`,
    not the database, since SQLite check constraints can't reference another table's column.
    """

    __tablename__ = "job_tent_sections"
    __table_args__ = (UniqueConstraint("job_tent_requirement_id", "sequence_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_tent_requirement_id: Mapped[int] = mapped_column(
        ForeignKey("job_tent_requirements.id", ondelete="CASCADE"), index=True
    )
    sequence_index: Mapped[int] = mapped_column(Integer)
    equipment_type_id: Mapped[int] = mapped_column(ForeignKey("equipment_types.id"))

    tent_requirement: Mapped[JobTentRequirement] = relationship(back_populates="sections")
    equipment_type: Mapped[EquipmentType] = relationship()


class JobEquipmentRequirement(Base):
    __tablename__ = "job_equipment_requirements"
    __table_args__ = (
        CheckConstraint("quantity_required > 0", name="quantity_positive"),
        CheckConstraint("releasable_at >= required_on_site_at", name="date_order"),
        UniqueConstraint("job_id", "equipment_type_id", "required_stage", "source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    job_tent_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_tent_requirements.id", ondelete="SET NULL")
    )
    equipment_type_id: Mapped[int] = mapped_column(ForeignKey("equipment_types.id"))
    quantity_required: Mapped[int] = mapped_column(Integer)
    required_on_site_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    releasable_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    required_stage: Mapped[BuildStage] = mapped_column(
        Enum(BuildStage, native_enum=False, length=40)
    )
    source: Mapped[RequirementSource] = mapped_column(
        Enum(RequirementSource, native_enum=False, length=20), default=RequirementSource.GENERATED
    )
    status: Mapped[RequirementStatus] = mapped_column(
        Enum(RequirementStatus, native_enum=False, length=30), default=RequirementStatus.UNRESOLVED
    )
    notes: Mapped[str | None] = mapped_column(Text)

    job: Mapped[Job] = relationship(back_populates="equipment_requirements")
    tent_requirement: Mapped[JobTentRequirement | None] = relationship()
    equipment_type: Mapped[EquipmentType] = relationship()
    assignments: Mapped[list[EquipmentAssignment]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )


class JobPhase(Base):
    """Build/Break apply to the whole site (`job_tent_requirement_id` null) — the same crew
    typically builds/strikes every tent on a job together. Up phases belong to one specific tent
    (`job_tent_requirement_id` set) since each tent has its own contract window; an Up phase's
    dates must fall within its tent's `contracted_up_at`/`contracted_down_at` (enforced in
    `JobService`, not the database, since SQLite check constraints can't join to another table).
    A tent's Up window can be freely split across several Up phases/Tentmasters (a crew handover
    mid-contract, overlap allowed for the handover day) via `JobService.add_phase()`/
    `delete_phase()` — phases are no longer purely auto-generated and re-synced.
    """

    __tablename__ = "job_phases"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="date_order"),
        CheckConstraint("required_headcount >= 0", name="headcount_nonnegative"),
        # Enum columns with native_enum=False persist the member *name* (e.g. "UP"), not
        # `.value` ("up") — matching the established convention elsewhere in this schema
        # (see the old CrewAssignment.override_type constraints this replaced).
        CheckConstraint(
            "phase_type != 'UP' OR job_tent_requirement_id IS NOT NULL", name="up_requires_tent"
        ),
        CheckConstraint(
            "phase_type = 'UP' OR job_tent_requirement_id IS NULL", name="only_up_has_tent"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    job_tent_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_tent_requirements.id", ondelete="CASCADE"), index=True
    )
    phase_type: Mapped[PhaseType] = mapped_column(
        Enum(PhaseType, native_enum=False, length=20), index=True
    )
    tentmaster_id: Mapped[int | None] = mapped_column(ForeignKey("tentmasters.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    end_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    required_headcount: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[RecordSource] = mapped_column(
        Enum(RecordSource, native_enum=False, length=20), default=RecordSource.GENERATED
    )

    job: Mapped[Job] = relationship(back_populates="phases")
    tentmaster: Mapped[Tentmaster | None] = relationship()
    tent_requirement: Mapped[JobTentRequirement | None] = relationship()


class LocalCrewBooking(Base):
    """Anonymous local/hired headcount booked onto a job between two dates — not tied to a
    specific phase. Joins whichever phase(s) are active during its window (see
    `roster.phase_roster()`), so moving/adjusting phases never requires re-entering local crew.
    """

    __tablename__ = "local_crew_bookings"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="date_order"),
        CheckConstraint("headcount > 0", name="headcount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    headcount: Mapped[int] = mapped_column(Integer)
    start_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    end_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    job: Mapped[Job] = relationship(back_populates="local_crew_bookings")
