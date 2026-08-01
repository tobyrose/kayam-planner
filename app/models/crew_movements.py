from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AwareDateTime, Base
from app.models.administration import CrewMember, Location, Tentmaster, Van
from app.models.logistics import MovementStatus


class JourneyMode(StrEnum):
    VAN = "van"
    LORRY = "lorry"
    FLIGHT = "flight"
    FERRY = "ferry"
    TRAIN = "train"
    TRANSFER = "transfer"
    OTHER = "other"


class CrewMovement(Base):
    __tablename__ = "crew_movements"
    __table_args__ = (CheckConstraint("arrive_by > depart_after", name="date_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    movement_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    origin_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    destination_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    tentmaster_id: Mapped[int | None] = mapped_column(ForeignKey("tentmasters.id"), index=True)
    van_id: Mapped[int | None] = mapped_column(ForeignKey("vans.id"))
    depart_after: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    arrive_by: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    status: Mapped[MovementStatus] = mapped_column(
        Enum(MovementStatus, native_enum=False, length=20), default=MovementStatus.PLANNED
    )
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    origin: Mapped[Location] = relationship(foreign_keys=[origin_location_id])
    destination: Mapped[Location] = relationship(foreign_keys=[destination_location_id])
    tentmaster: Mapped[Tentmaster | None] = relationship()
    van: Mapped[Van | None] = relationship()
    legs: Mapped[list[CrewJourneyLeg]] = relationship(
        back_populates="movement", cascade="all, delete-orphan", order_by="CrewJourneyLeg.sequence"
    )
    passengers: Mapped[list[CrewMovementPassenger]] = relationship(
        back_populates="movement", cascade="all, delete-orphan"
    )


class CrewJourneyLeg(Base):
    __tablename__ = "crew_journey_legs"
    __table_args__ = (
        UniqueConstraint("crew_movement_id", "sequence"),
        CheckConstraint("sequence > 0", name="sequence_positive"),
        CheckConstraint("arrive_at > depart_at", name="date_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crew_movement_id: Mapped[int] = mapped_column(
        ForeignKey("crew_movements.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    mode: Mapped[JourneyMode] = mapped_column(Enum(JourneyMode, native_enum=False, length=20))
    origin_label: Mapped[str] = mapped_column(String(200))
    destination_label: Mapped[str] = mapped_column(String(200))
    depart_at: Mapped[datetime] = mapped_column(AwareDateTime())
    arrive_at: Mapped[datetime] = mapped_column(AwareDateTime())
    booking_reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    movement: Mapped[CrewMovement] = relationship(back_populates="legs")


class CrewMovementPassenger(Base):
    __tablename__ = "crew_movement_passengers"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "(crew_member_id IS NOT NULL AND placeholder_label IS NULL AND quantity = 1) "
            "OR (crew_member_id IS NULL AND placeholder_label IS NOT NULL)",
            name="named_or_placeholder",
        ),
        UniqueConstraint("crew_movement_id", "crew_member_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crew_movement_id: Mapped[int] = mapped_column(
        ForeignKey("crew_movements.id", ondelete="CASCADE"), index=True
    )
    crew_member_id: Mapped[int | None] = mapped_column(ForeignKey("crew_members.id"))
    placeholder_label: Mapped[str | None] = mapped_column(String(150))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    joining_tentmaster_id: Mapped[int | None] = mapped_column(ForeignKey("tentmasters.id"))
    leaving_tentmaster_id: Mapped[int | None] = mapped_column(ForeignKey("tentmasters.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    movement: Mapped[CrewMovement] = relationship(back_populates="passengers")
    crew_member: Mapped[CrewMember | None] = relationship()
    joining_tentmaster: Mapped[Tentmaster | None] = relationship(
        foreign_keys=[joining_tentmaster_id]
    )
    leaving_tentmaster: Mapped[Tentmaster | None] = relationship(
        foreign_keys=[leaving_tentmaster_id]
    )
