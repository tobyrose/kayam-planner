from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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

if TYPE_CHECKING:
    from app.models.equipment_planning import EquipmentAssignment


def utc_now() -> datetime:
    return datetime.now(UTC)


class LocationType(StrEnum):
    SITE = "site"
    YARD = "yard"
    DEPOT = "depot"
    WORKSHOP = "workshop"
    AIRPORT = "airport"
    FERRY_PORT = "ferry_port"
    OTHER = "other"


class TrackingMode(StrEnum):
    INDIVIDUAL = "individual"
    QUANTITY = "quantity"


class BuildStage(StrEnum):
    SITE_PREPARATION = "site_preparation"
    POLES_AND_ANCHORS = "poles_and_anchors"
    MAIN_SECTIONS = "main_sections"
    COMPLETION_AND_ANCILLARY = "completion_and_ancillary"
    MAINTENANCE = "maintenance"
    STRIKE = "strike"


class CrewAvailabilityStatus(StrEnum):
    UNAVAILABLE = "unavailable"
    LEAVE = "leave"
    TRAINING = "training"
    RESTRICTED = "restricted"
    AVAILABLE_OVERRIDE = "available_override"


class OwnershipType(StrEnum):
    OWNED = "owned"
    HIRED = "hired"
    SUPPLIER = "supplier"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )


class Location(TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="longitude_range",
        ),
        CheckConstraint("default_unload_duration_minutes >= 0", name="unload_duration_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    location_type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, native_enum=False, length=20), default=LocationType.SITE
    )
    address_line_1: Mapped[str | None] = mapped_column(String(200))
    address_line_2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    postcode: Mapped[str | None] = mapped_column(String(30))
    country_code: Mapped[str] = mapped_column(String(2), default="GB")
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    timezone: Mapped[str] = mapped_column(String(100), default="Europe/London")
    geocoding_provider: Mapped[str | None] = mapped_column(String(50))
    geocoding_place_id: Mapped[str | None] = mapped_column(String(200))
    geocoded_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    access_notes: Mapped[str | None] = mapped_column(Text)
    hgv_notes: Mapped[str | None] = mapped_column(Text)
    receiving_notes: Mapped[str | None] = mapped_column(Text)
    default_unload_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TentFamily(Base):
    """A family (Kayam, Valhalla, ...) defines how its own section sequences derive poles.

    `pole_count_multiplier`/`pole_count_offset` implement `poles = sections * multiplier +
    offset` (Kayam's known formula is sections*2-2, i.e. multiplier=2, offset=-2), and
    `pole_equipment_type_id` says which equipment type's assets fulfil that derived pole
    requirement (its `pack_size` — e.g. 2 for a "pair" pole type — converts the physical pole
    count into an asset quantity). Configurable per family rather than hardcoded, since a
    different family may use a different formula or pole type.
    """

    __tablename__ = "tent_families"
    __table_args__ = (
        CheckConstraint("pole_count_multiplier != 0", name="pole_multiplier_nonzero"),
        CheckConstraint("default_build_hours >= 0", name="build_hours_nonnegative"),
        CheckConstraint("default_strike_hours >= 0", name="strike_hours_nonnegative"),
        CheckConstraint("minimum_crew >= 0", name="minimum_crew_nonnegative"),
        CheckConstraint("preferred_crew >= minimum_crew", name="preferred_crew_minimum"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    pole_equipment_type_id: Mapped[int | None] = mapped_column(ForeignKey("equipment_types.id"))
    pole_count_multiplier: Mapped[int] = mapped_column(Integer, default=2)
    pole_count_offset: Mapped[int] = mapped_column(Integer, default=-2)
    # Per-tent build/strike duration and crew defaults used to be per named TentConfiguration
    # (e.g. "Kayam 10-pole"); simplified to per-family since size is now derived from the section
    # sequence, not a named template. Still overridable per job (JobTentRequirement's own
    # *_override fields).
    default_build_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    default_strike_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    minimum_crew: Mapped[int] = mapped_column(Integer, default=0)
    preferred_crew: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    equipment_types: Mapped[list[EquipmentType]] = relationship(
        back_populates="tent_family", foreign_keys="EquipmentType.tent_family_id"
    )
    pole_equipment_type: Mapped[EquipmentType | None] = relationship(
        foreign_keys=[pole_equipment_type_id]
    )


class EquipmentType(Base):
    """`category` distinguishes what a type is for in the section-sequence model:

    - "section": a bookable tent section (K, M, m, S, T, SC, V, ...) — the only categories a
      planner may type into a job's section sequence.
    - "pole": a derived pole type (P, X) — never typed directly; quantity is computed from the
      section count via the owning `TentFamily`'s formula.
    - "linked": equipment implied by a section or pole via `EquipmentLink`, never entered
      directly and never shown on the main loading list, only in a load's detailed view.
    - "ancillary": individually tracked equipment unrelated to any tent sequence (Auger Driver,
      Stake Basher, Rock Drill, Crew Tent, ...), added to jobs/loads manually as needed.

    `pack_size` is how many physical units one tracked asset of this type represents (e.g. 2 for
    a pole type sold/tracked as a pair) — used to convert a physical quantity into an asset
    quantity when expanding requirements.
    """

    __tablename__ = "equipment_types"
    __table_args__ = (
        CheckConstraint("section_capacity_units >= 0", name="section_units_nonnegative"),
        CheckConstraint("pole_capacity_units >= 0", name="pole_units_nonnegative"),
        CheckConstraint("ancillary_capacity_units >= 0", name="ancillary_units_nonnegative"),
        CheckConstraint("weight_kg >= 0", name="weight_nonnegative"),
        CheckConstraint("pack_size > 0", name="pack_size_positive"),
        CheckConstraint(
            "maintenance_interval_days IS NULL OR maintenance_interval_days >= 0",
            name="maintenance_interval_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(100))
    tent_family_id: Mapped[int | None] = mapped_column(ForeignKey("tent_families.id"))
    tracking_mode: Mapped[TrackingMode] = mapped_column(
        Enum(TrackingMode, native_enum=False, length=20), default=TrackingMode.INDIVIDUAL
    )
    pack_size: Mapped[int] = mapped_column(Integer, default=1)
    section_capacity_units: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    pole_capacity_units: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    ancillary_capacity_units: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    default_build_stage: Mapped[BuildStage] = mapped_column(
        Enum(BuildStage, native_enum=False, length=40),
        default=BuildStage.COMPLETION_AND_ANCILLARY,
    )
    maintenance_interval_days: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    tent_family: Mapped[TentFamily | None] = relationship(
        back_populates="equipment_types", foreign_keys=[tent_family_id]
    )
    assets: Mapped[list[EquipmentAsset]] = relationship(back_populates="equipment_type")
    outgoing_links: Mapped[list[EquipmentLink]] = relationship(
        back_populates="parent_equipment_type",
        foreign_keys="EquipmentLink.parent_equipment_type_id",
        cascade="all, delete-orphan",
    )


class EquipmentAsset(TimestampMixin, Base):
    __tablename__ = "equipment_assets"
    __table_args__ = (
        CheckConstraint(
            "replacement_value IS NULL OR replacement_value >= 0",
            name="replacement_value_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    equipment_type_id: Mapped[int] = mapped_column(ForeignKey("equipment_types.id"))
    variant: Mapped[str | None] = mapped_column(String(100))
    generation: Mapped[str | None] = mapped_column(String(100))
    initial_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    current_status: Mapped[str] = mapped_column(String(50), default="available")
    serviceable: Mapped[bool] = mapped_column(Boolean, default=True)
    commissioned_date: Mapped[date | None] = mapped_column(Date)
    retired_date: Mapped[date | None] = mapped_column(Date)
    replacement_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    equipment_type: Mapped[EquipmentType] = relationship(back_populates="assets")
    initial_location: Mapped[Location | None] = relationship()
    assignments: Mapped[list[EquipmentAssignment]] = relationship(back_populates="equipment_asset")


class EquipmentLink(Base):
    """A cascading BOM edge: booking one `parent_equipment_type` implies `quantity_per_parent`
    of `child_equipment_type`, recursively (a child may itself be a parent of further links).

    Admin-editable, matching how the old flat `TentConfigurationRequirement` BOM worked, but
    keyed to individual equipment types rather than a named tent template so it cascades through
    any depth (e.g. M -> side pole, M -> anchor stillage, M -> bale ring; P -> side guy, P ->
    Tifor). `app/services/roster.py`-style expansion code guards against cycles defensively even
    though this direct self-link check catches the simplest case at write time.
    """

    __tablename__ = "equipment_links"
    __table_args__ = (
        UniqueConstraint("parent_equipment_type_id", "child_equipment_type_id"),
        CheckConstraint("quantity_per_parent > 0", name="quantity_positive"),
        CheckConstraint(
            "parent_equipment_type_id != child_equipment_type_id", name="no_self_link"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_equipment_type_id: Mapped[int] = mapped_column(
        ForeignKey("equipment_types.id", ondelete="CASCADE")
    )
    child_equipment_type_id: Mapped[int] = mapped_column(ForeignKey("equipment_types.id"))
    quantity_per_parent: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    parent_equipment_type: Mapped[EquipmentType] = relationship(
        back_populates="outgoing_links", foreign_keys=[parent_equipment_type_id]
    )
    child_equipment_type: Mapped[EquipmentType] = relationship(
        foreign_keys=[child_equipment_type_id]
    )


class CrewRole(Base):
    __tablename__ = "crew_roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CrewEmploymentType(Base):
    __tablename__ = "crew_employment_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CrewMember(Base):
    __tablename__ = "crew_members"
    __table_args__ = (
        CheckConstraint("hourly_cost >= 0", name="hourly_cost_nonnegative"),
        CheckConstraint("overtime_hourly_cost >= 0", name="overtime_cost_nonnegative"),
        CheckConstraint("travel_hourly_cost >= 0", name="travel_cost_nonnegative"),
        CheckConstraint("daily_allowance >= 0", name="daily_allowance_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("crew_roles.id"))
    employment_type_id: Mapped[int] = mapped_column(ForeignKey("crew_employment_types.id"))
    hourly_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    overtime_hourly_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    travel_hourly_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    daily_allowance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    can_drive_van: Mapped[bool] = mapped_column(Boolean, default=False)
    can_drive_hgv: Mapped[bool] = mapped_column(Boolean, default=False)
    skills: Mapped[str | None] = mapped_column(Text)
    home_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    role: Mapped[CrewRole] = relationship()
    employment_type: Mapped[CrewEmploymentType] = relationship()
    home_location: Mapped[Location | None] = relationship()
    memberships: Mapped[list[TentmasterMembership]] = relationship(back_populates="crew_member")
    availability: Mapped[list[CrewAvailability]] = relationship(
        back_populates="crew_member", cascade="all, delete-orphan"
    )
    availability_windows: Mapped[list[CrewAvailabilityWindow]] = relationship(
        back_populates="crew_member", cascade="all, delete-orphan"
    )


class LorryType(Base):
    __tablename__ = "lorry_types"
    __table_args__ = (
        CheckConstraint("section_capacity_units >= 0", name="section_units_nonnegative"),
        CheckConstraint("pole_capacity_units >= 0", name="pole_units_nonnegative"),
        CheckConstraint("ancillary_capacity_units >= 0", name="ancillary_units_nonnegative"),
        CheckConstraint("payload_kg >= 0", name="payload_nonnegative"),
        CheckConstraint("passenger_capacity >= 0", name="passenger_capacity_nonnegative"),
        CheckConstraint("default_cost_per_km >= 0", name="cost_per_km_nonnegative"),
        CheckConstraint("minimum_load_cost >= 0", name="minimum_load_cost_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    section_capacity_units: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    pole_capacity_units: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    ancillary_capacity_units: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    payload_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    passenger_capacity: Mapped[int] = mapped_column(Integer, default=0)
    default_cost_per_km: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    minimum_load_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    lorries: Mapped[list[Lorry]] = relationship(back_populates="lorry_type")


class Haulier(Base):
    __tablename__ = "hauliers"
    __table_args__ = (
        CheckConstraint("default_cost_per_km >= 0", name="cost_per_km_nonnegative"),
        CheckConstraint("minimum_load_cost >= 0", name="minimum_load_cost_nonnegative"),
        CheckConstraint("waiting_hourly_cost >= 0", name="waiting_cost_nonnegative"),
        CheckConstraint("fuel_surcharge_percent >= 0", name="fuel_surcharge_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    contact_name: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    default_cost_per_km: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    minimum_load_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    waiting_hourly_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    fuel_surcharge_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    lorries: Mapped[list[Lorry]] = relationship(back_populates="haulier")


class Van(Base):
    __tablename__ = "vans"
    __table_args__ = (
        CheckConstraint("passenger_capacity >= 0", name="passenger_capacity_nonnegative"),
        CheckConstraint("cargo_capacity_units >= 0", name="cargo_capacity_nonnegative"),
        CheckConstraint("cost_per_km >= 0", name="cost_per_km_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_or_name: Mapped[str] = mapped_column(String(100), unique=True)
    passenger_capacity: Mapped[int] = mapped_column(Integer, default=0)
    cargo_capacity_units: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    home_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    ownership_type: Mapped[OwnershipType] = mapped_column(
        Enum(OwnershipType, native_enum=False, length=20), default=OwnershipType.OWNED
    )
    cost_per_km: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    home_location: Mapped[Location] = relationship()


class Tentmaster(Base):
    __tablename__ = "tentmasters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    lead_crew_member_id: Mapped[int | None] = mapped_column(ForeignKey("crew_members.id"))
    home_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    default_van_id: Mapped[int | None] = mapped_column(ForeignKey("vans.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    lead_crew_member: Mapped[CrewMember | None] = relationship(foreign_keys=[lead_crew_member_id])
    home_location: Mapped[Location | None] = relationship()
    default_van: Mapped[Van | None] = relationship()
    memberships: Mapped[list[TentmasterMembership]] = relationship(back_populates="tentmaster")


class TentmasterMembership(Base):
    """`end_at` is exclusive: "first day no longer active." Open-ended when NULL.

    Half-open boundaries (rather than an inclusive last working day) let a crew member end with
    one Tentmaster and start with another on the same calendar date.
    """

    __tablename__ = "tentmaster_memberships"
    __table_args__ = (CheckConstraint("end_at IS NULL OR end_at > start_at", name="date_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tentmaster_id: Mapped[int] = mapped_column(ForeignKey("tentmasters.id"))
    crew_member_id: Mapped[int] = mapped_column(ForeignKey("crew_members.id"), index=True)
    start_at: Mapped[date] = mapped_column(Date)
    end_at: Mapped[date | None] = mapped_column(Date)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    tentmaster: Mapped[Tentmaster] = relationship(back_populates="memberships")
    crew_member: Mapped[CrewMember] = relationship(back_populates="memberships")


class CrewAvailability(Base):
    __tablename__ = "crew_availability"
    __table_args__ = (CheckConstraint("end_at >= start_at", name="date_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crew_member_id: Mapped[int] = mapped_column(ForeignKey("crew_members.id"), index=True)
    start_at: Mapped[date] = mapped_column(Date)
    end_at: Mapped[date] = mapped_column(Date)
    status: Mapped[CrewAvailabilityStatus] = mapped_column(
        Enum(CrewAvailabilityStatus, native_enum=False, length=30)
    )
    notes: Mapped[str | None] = mapped_column(Text)

    crew_member: Mapped[CrewMember] = relationship(back_populates="availability")


class CrewAvailabilityWindow(Base):
    """An explicit window during which a crew member can work at all (e.g. a season contract).

    Multiple windows are allowed per crew member (25 May-17 Jun, then 28 Jun-31 Dec, etc), and
    dates are inclusive at both ends, matching `CrewAvailability`. If a crew member has no windows
    at all, they are treated as always available -- this constrains membership derivation only
    when a window has been entered, rather than requiring one for every crew member up front.
    """

    __tablename__ = "crew_availability_windows"
    __table_args__ = (CheckConstraint("end_at IS NULL OR end_at >= start_at", name="date_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crew_member_id: Mapped[int] = mapped_column(ForeignKey("crew_members.id"), index=True)
    start_at: Mapped[date] = mapped_column(Date)
    end_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    crew_member: Mapped[CrewMember] = relationship(back_populates="availability_windows")


class Lorry(Base):
    __tablename__ = "lorries"

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_or_name: Mapped[str] = mapped_column(String(100), unique=True)
    lorry_type_id: Mapped[int] = mapped_column(ForeignKey("lorry_types.id"))
    haulier_id: Mapped[int | None] = mapped_column(ForeignKey("hauliers.id"))
    ownership_type: Mapped[OwnershipType] = mapped_column(
        Enum(OwnershipType, native_enum=False, length=20), default=OwnershipType.OWNED
    )
    home_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    lorry_type: Mapped[LorryType] = relationship(back_populates="lorries")
    haulier: Mapped[Haulier | None] = relationship(back_populates="lorries")
    home_location: Mapped[Location | None] = relationship()
