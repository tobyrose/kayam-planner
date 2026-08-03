from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AwareDateTime, Base
from app.models.administration import CrewMember, Tentmaster


class CrewActivityType(StrEnum):
    TRAINING = "training"
    LEAVE = "leave"
    YARD_WORK = "yard_work"
    CLEANING = "cleaning"
    TRAVEL = "travel"
    OTHER = "other"


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
