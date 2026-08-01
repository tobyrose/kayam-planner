from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AwareDateTime, Base
from app.models.administration import EquipmentAsset, EquipmentType
from app.models.jobs import JobEquipmentRequirement, RecordSource


class AllocationStrength(StrEnum):
    SOFT = "soft"
    HARD = "hard"


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class EquipmentCompatibility(Base):
    __tablename__ = "equipment_compatibility"
    __table_args__ = (
        UniqueConstraint("required_equipment_type_id", "compatible_equipment_type_id"),
        CheckConstraint(
            "required_equipment_type_id != compatible_equipment_type_id",
            name="different_types",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    required_equipment_type_id: Mapped[int] = mapped_column(ForeignKey("equipment_types.id"))
    compatible_equipment_type_id: Mapped[int] = mapped_column(ForeignKey("equipment_types.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    required_equipment_type: Mapped[EquipmentType] = relationship(
        foreign_keys=[required_equipment_type_id]
    )
    compatible_equipment_type: Mapped[EquipmentType] = relationship(
        foreign_keys=[compatible_equipment_type_id]
    )


class EquipmentAssignment(Base):
    __tablename__ = "equipment_assignments"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="date_order"),
        UniqueConstraint("job_equipment_requirement_id", "equipment_asset_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_equipment_requirement_id: Mapped[int] = mapped_column(
        ForeignKey("job_equipment_requirements.id", ondelete="CASCADE"), index=True
    )
    equipment_asset_id: Mapped[int] = mapped_column(ForeignKey("equipment_assets.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    end_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    allocation_strength: Mapped[AllocationStrength] = mapped_column(
        Enum(AllocationStrength, native_enum=False, length=10),
        default=AllocationStrength.SOFT,
        index=True,
    )
    assignment_source: Mapped[RecordSource] = mapped_column(
        Enum(RecordSource, native_enum=False, length=20), default=RecordSource.MANUAL
    )
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, native_enum=False, length=20), default=AssignmentStatus.ACTIVE
    )
    notes: Mapped[str | None] = mapped_column(Text)

    requirement: Mapped[JobEquipmentRequirement] = relationship(back_populates="assignments")
    equipment_asset: Mapped[EquipmentAsset] = relationship(back_populates="assignments")
