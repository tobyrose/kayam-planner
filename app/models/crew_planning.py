from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AwareDateTime, Base
from app.models.administration import CrewMember, Tentmaster
from app.models.jobs import JobPhase, RecordSource


class CrewActivityType(StrEnum):
    TRAINING = "training"
    LEAVE = "leave"
    YARD_WORK = "yard_work"
    TRAVEL = "travel"
    OTHER = "other"


class CrewAssignment(Base):
    __tablename__ = "crew_assignments"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="date_order"),
        CheckConstraint(
            "(crew_member_id IS NOT NULL AND placeholder_name IS NULL) OR "
            "(crew_member_id IS NULL AND placeholder_name IS NOT NULL)",
            name="person_or_placeholder",
        ),
        CheckConstraint(
            "hourly_cost_override IS NULL OR hourly_cost_override >= 0",
            name="hourly_cost_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_phase_id: Mapped[int] = mapped_column(
        ForeignKey("job_phases.id", ondelete="CASCADE"), index=True
    )
    crew_member_id: Mapped[int | None] = mapped_column(ForeignKey("crew_members.id"), index=True)
    placeholder_name: Mapped[str | None] = mapped_column(String(150))
    tentmaster_id: Mapped[int | None] = mapped_column(ForeignKey("tentmasters.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    end_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    role: Mapped[str] = mapped_column(String(100), default="Crew")
    assignment_source: Mapped[RecordSource] = mapped_column(
        Enum(RecordSource, native_enum=False, length=20), default=RecordSource.MANUAL
    )
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    hourly_cost_override: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    job_phase: Mapped[JobPhase] = relationship(back_populates="crew_assignments")
    crew_member: Mapped[CrewMember | None] = relationship()
    tentmaster: Mapped[Tentmaster | None] = relationship()


class CrewActivity(Base):
    __tablename__ = "crew_activities"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="date_order"),
        CheckConstraint("required_headcount >= 0", name="headcount_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_type: Mapped[CrewActivityType] = mapped_column(
        Enum(CrewActivityType, native_enum=False, length=20), index=True
    )
    tentmaster_id: Mapped[int | None] = mapped_column(ForeignKey("tentmasters.id"), index=True)
    crew_member_id: Mapped[int | None] = mapped_column(ForeignKey("crew_members.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    end_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    required_headcount: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)

    tentmaster: Mapped[Tentmaster | None] = relationship()
    crew_member: Mapped[CrewMember | None] = relationship()
