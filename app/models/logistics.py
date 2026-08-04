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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AwareDateTime, Base
from app.models.administration import EquipmentAsset, EquipmentType, Location, Lorry, LorryType
from app.models.jobs import RecordSource


class MovementStatus(StrEnum):
    REQUIRED = "required"
    PLANNED = "planned"
    CONFIRMED = "confirmed"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LoadStatus(StrEnum):
    DRAFT = "draft"
    PLANNED = "planned"
    CONFIRMED = "confirmed"
    LOADING = "loading"
    DEPARTED = "departed"
    ARRIVED = "arrived"
    UNLOADED = "unloaded"
    CANCELLED = "cancelled"


class EstimateSource(StrEnum):
    CALCULATED = "calculated"
    MANUAL = "manual"


class EquipmentMovement(Base):
    __tablename__ = "equipment_movements"
    __table_args__ = (
        CheckConstraint("arrive_by > depart_after", name="date_order"),
        CheckConstraint("loading_minutes >= 0", name="loading_nonnegative"),
        CheckConstraint("unloading_minutes >= 0", name="unloading_nonnegative"),
        CheckConstraint("contingency_minutes >= 0", name="contingency_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    movement_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    origin_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    destination_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    depart_after: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    arrive_by: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    loading_minutes: Mapped[int] = mapped_column(Integer, default=60)
    unloading_minutes: Mapped[int] = mapped_column(Integer, default=60)
    contingency_minutes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[MovementStatus] = mapped_column(
        Enum(MovementStatus, native_enum=False, length=20), default=MovementStatus.REQUIRED
    )
    source: Mapped[RecordSource] = mapped_column(
        Enum(RecordSource, native_enum=False, length=20), default=RecordSource.MANUAL
    )
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    origin: Mapped[Location] = relationship(foreign_keys=[origin_location_id])
    destination: Mapped[Location] = relationship(foreign_keys=[destination_location_id])
    loads: Mapped[list[Load]] = relationship(
        back_populates="movement", cascade="all, delete-orphan", order_by="Load.load_number"
    )

    @property
    def operational_allowance_minutes(self) -> int:
        return self.loading_minutes + self.unloading_minutes + self.contingency_minutes


class Load(Base):
    __tablename__ = "loads"
    __table_args__ = (
        UniqueConstraint("equipment_movement_id", "load_number"),
        CheckConstraint("load_number > 0", name="load_number_positive"),
        CheckConstraint("estimated_cost >= 0", name="estimated_cost_nonnegative"),
        CheckConstraint("actual_cost >= 0", name="actual_cost_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_movement_id: Mapped[int] = mapped_column(
        ForeignKey("equipment_movements.id", ondelete="CASCADE"), index=True
    )
    load_number: Mapped[int] = mapped_column(Integer)
    lorry_id: Mapped[int | None] = mapped_column(ForeignKey("lorries.id"))
    lorry_type_id: Mapped[int] = mapped_column(ForeignKey("lorry_types.id"))
    status: Mapped[LoadStatus] = mapped_column(
        Enum(LoadStatus, native_enum=False, length=20), default=LoadStatus.DRAFT, index=True
    )
    planned_departure_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    planned_arrival_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    actual_departure_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    actual_arrival_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    driver_name: Mapped[str | None] = mapped_column(String(150))
    estimated_distance_km: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    estimate_source: Mapped[EstimateSource] = mapped_column(
        Enum(EstimateSource, native_enum=False, length=20), default=EstimateSource.CALCULATED
    )
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    movement: Mapped[EquipmentMovement] = relationship(back_populates="loads")
    lorry: Mapped[Lorry | None] = relationship()
    lorry_type: Mapped[LorryType] = relationship()
    items: Mapped[list[LoadItem]] = relationship(
        back_populates="load", cascade="all, delete-orphan"
    )

    @property
    def display_code(self) -> str:
        """Planner-facing load label — simple L-number (e.g. L1), not movement codes."""
        return f"L{self.load_number}"


class LoadItem(Base):
    __tablename__ = "load_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "(equipment_asset_id IS NOT NULL AND equipment_type_id IS NULL AND quantity = 1) "
            "OR (equipment_asset_id IS NULL AND equipment_type_id IS NOT NULL)",
            name="asset_or_quantity_type",
        ),
        UniqueConstraint("load_id", "equipment_asset_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    load_id: Mapped[int] = mapped_column(ForeignKey("loads.id", ondelete="CASCADE"), index=True)
    equipment_asset_id: Mapped[int | None] = mapped_column(ForeignKey("equipment_assets.id"))
    equipment_type_id: Mapped[int | None] = mapped_column(ForeignKey("equipment_types.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text)

    load: Mapped[Load] = relationship(back_populates="items")
    equipment_asset: Mapped[EquipmentAsset | None] = relationship()
    equipment_type: Mapped[EquipmentType | None] = relationship()

    @property
    def resolved_type(self) -> EquipmentType:
        if self.equipment_asset is not None:
            return self.equipment_asset.equipment_type
        assert self.equipment_type is not None
        return self.equipment_type


class RouteCache(Base):
    __tablename__ = "route_cache"
    __table_args__ = (
        UniqueConstraint("cache_key"),
        CheckConstraint("distance_km >= 0", name="distance_nonnegative"),
        CheckConstraint("driving_duration_minutes >= 0", name="duration_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    origin_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    destination_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    vehicle_profile: Mapped[str] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(50))
    distance_km: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    driving_duration_minutes: Mapped[int] = mapped_column(Integer)
    calculated_at: Mapped[datetime] = mapped_column(AwareDateTime())
    manual: Mapped[bool] = mapped_column(Boolean, default=False)

    origin: Mapped[Location] = relationship(foreign_keys=[origin_location_id])
    destination: Mapped[Location] = relationship(foreign_keys=[destination_location_id])
