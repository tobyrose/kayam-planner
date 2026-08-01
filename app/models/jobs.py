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
    TentConfiguration,
    Tentmaster,
    utc_now,
)

if TYPE_CHECKING:
    from app.models.crew_planning import CrewAssignment
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
    SITE_PREP = "site_prep"
    BUILD = "build"
    HANDOVER = "handover"
    SHOW = "show"
    MAINTENANCE = "maintenance"
    STRIKE = "strike"
    CLEAR_SITE = "clear_site"
    OTHER = "other"


class RecordSource(StrEnum):
    GENERATED = "generated"
    MANUAL = "manual"
    SUGGESTED = "suggested"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "confidence_percent IS NULL OR confidence_percent BETWEEN 0 AND 100",
            name="confidence_range",
        ),
        CheckConstraint("contract_revenue >= 0", name="contract_revenue_nonnegative"),
        CheckConstraint("local_crew_supplied >= 0", name="local_crew_supplied_nonnegative"),
        CheckConstraint("local_crew_required >= 0", name="local_crew_required_nonnegative"),
        CheckConstraint("must_be_up_at >= site_access_at", name="access_before_up"),
        CheckConstraint("strike_available_at >= must_be_up_at", name="up_before_strike"),
        CheckConstraint(
            "show_end_at IS NULL OR show_start_at IS NULL OR show_end_at >= show_start_at",
            name="show_date_order",
        ),
        CheckConstraint(
            "site_clear_by IS NULL OR site_clear_by >= strike_available_at",
            name="strike_before_clear",
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
    site_access_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    must_be_up_at: Mapped[datetime] = mapped_column(AwareDateTime())
    show_start_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    show_end_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    strike_available_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    site_clear_by: Mapped[datetime | None] = mapped_column(AwareDateTime())
    maintenance_cover_required: Mapped[bool] = mapped_column(Boolean, default=False)
    catering_arrangement: Mapped[str | None] = mapped_column(Text)
    accommodation_arrangement: Mapped[str | None] = mapped_column(Text)
    ground_type: Mapped[str | None] = mapped_column(String(100))
    local_crew_supplied: Mapped[int] = mapped_column(Integer, default=0)
    local_crew_required: Mapped[int] = mapped_column(Integer, default=0)
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


class JobTentRequirement(Base):
    __tablename__ = "job_tent_requirements"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    tent_configuration_id: Mapped[int] = mapped_column(ForeignKey("tent_configurations.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    custom_name: Mapped[str | None] = mapped_column(String(200))
    build_start_override: Mapped[datetime | None] = mapped_column(AwareDateTime())
    build_duration_override_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    strike_duration_override_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    required_crew_override: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    job: Mapped[Job] = relationship(back_populates="tent_requirements")
    tent_configuration: Mapped[TentConfiguration] = relationship()


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
    __tablename__ = "job_phases"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="date_order"),
        CheckConstraint("required_headcount >= 0", name="headcount_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
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
    crew_assignments: Mapped[list[CrewAssignment]] = relationship(
        back_populates="job_phase", cascade="all, delete-orphan"
    )
