from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.administration import (
    BuildStage,
    CrewAvailabilityStatus,
    LocationType,
    OwnershipType,
    TrackingMode,
)


class AdministrationData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LocationData(AdministrationData):
    name: str = Field(min_length=1, max_length=200)
    location_type: LocationType = LocationType.SITE
    address_line_1: str | None = Field(default=None, max_length=200)
    address_line_2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postcode: str | None = Field(default=None, max_length=30)
    country_code: str = Field(default="GB", min_length=2, max_length=2)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    timezone: str = Field(default="Europe/London", min_length=1, max_length=100)
    access_notes: str | None = None
    hgv_notes: str | None = None
    receiving_notes: str | None = None
    default_unload_duration_minutes: int = Field(default=60, ge=0)
    active: bool = True

    @field_validator("country_code")
    @classmethod
    def normalise_country_code(cls, value: str) -> str:
        return value.upper()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Enter a valid IANA timezone, such as Europe/London") from error
        return value


class TentFamilyData(AdministrationData):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    active: bool = True


class EquipmentTypeData(AdministrationData):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=100)
    tent_family_id: int | None = None
    tracking_mode: TrackingMode = TrackingMode.INDIVIDUAL
    section_capacity_units: Decimal = Field(default=Decimal("0"), ge=0)
    pole_capacity_units: Decimal = Field(default=Decimal("0"), ge=0)
    ancillary_capacity_units: Decimal = Field(default=Decimal("0"), ge=0)
    weight_kg: Decimal = Field(default=Decimal("0"), ge=0)
    default_build_stage: BuildStage = BuildStage.COMPLETION_AND_ANCILLARY
    maintenance_interval_days: int | None = Field(default=None, ge=0)
    active: bool = True
    notes: str | None = None

    @field_validator("code")
    @classmethod
    def normalise_code(cls, value: str) -> str:
        return value.upper()


class EquipmentAssetData(AdministrationData):
    asset_code: str = Field(min_length=1, max_length=50)
    equipment_type_id: int
    variant: str | None = Field(default=None, max_length=100)
    generation: str | None = Field(default=None, max_length=100)
    initial_location_id: int | None = None
    current_status: str = Field(default="available", min_length=1, max_length=50)
    serviceable: bool = True
    commissioned_date: date | None = None
    retired_date: date | None = None
    replacement_value: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    active: bool = True

    @field_validator("asset_code")
    @classmethod
    def normalise_asset_code(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_lifecycle_dates(self) -> Self:
        if (
            self.commissioned_date is not None
            and self.retired_date is not None
            and self.retired_date < self.commissioned_date
        ):
            raise ValueError("Retired date cannot be before commissioned date")
        return self


class TentConfigurationData(AdministrationData):
    tent_family_id: int
    name: str = Field(min_length=1, max_length=100)
    pole_count: int = Field(gt=0)
    width_m: Decimal | None = Field(default=None, gt=0)
    length_m: Decimal | None = Field(default=None, gt=0)
    default_build_hours: Decimal = Field(default=Decimal("0"), ge=0)
    default_strike_hours: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_crew: int = Field(default=0, ge=0)
    preferred_crew: int = Field(default=0, ge=0)
    active: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def validate_crew_levels(self) -> Self:
        if self.preferred_crew < self.minimum_crew:
            raise ValueError("Preferred crew cannot be lower than minimum crew")
        return self


class TentConfigurationRequirementData(AdministrationData):
    tent_configuration_id: int
    equipment_type_id: int
    quantity: int = Field(gt=0)
    required_stage: BuildStage
    individually_assignable: bool = True


class CrewMemberData(AdministrationData):
    name: str = Field(min_length=1, max_length=150)
    role: str = Field(min_length=1, max_length=100)
    employment_type: str = Field(min_length=1, max_length=100)
    hourly_cost: Decimal = Field(default=Decimal("0"), ge=0)
    overtime_hourly_cost: Decimal = Field(default=Decimal("0"), ge=0)
    travel_hourly_cost: Decimal = Field(default=Decimal("0"), ge=0)
    daily_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    can_drive_van: bool = False
    can_drive_hgv: bool = False
    skills: str | None = None
    home_location_id: int | None = None
    active: bool = True
    notes: str | None = None


class TentmasterData(AdministrationData):
    name: str = Field(min_length=1, max_length=150)
    lead_crew_member_id: int | None = None
    home_location_id: int | None = None
    default_van_id: int | None = None
    active: bool = True
    notes: str | None = None


class TentmasterMembershipData(AdministrationData):
    tentmaster_id: int
    crew_member_id: int
    start_at: date
    end_at: date | None = None
    is_default: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def validate_date_order(self) -> Self:
        if self.end_at is not None and self.end_at < self.start_at:
            raise ValueError("End date cannot be before start date")
        return self


class CrewAvailabilityData(AdministrationData):
    crew_member_id: int
    start_at: date
    end_at: date
    status: CrewAvailabilityStatus
    notes: str | None = None

    @model_validator(mode="after")
    def validate_date_order(self) -> Self:
        if self.end_at < self.start_at:
            raise ValueError("End date cannot be before start date")
        return self


class LorryTypeData(AdministrationData):
    name: str = Field(min_length=1, max_length=100)
    section_capacity_units: Decimal = Field(default=Decimal("0"), ge=0)
    pole_capacity_units: Decimal = Field(default=Decimal("0"), ge=0)
    ancillary_capacity_units: Decimal = Field(default=Decimal("0"), ge=0)
    payload_kg: Decimal = Field(default=Decimal("0"), ge=0)
    passenger_capacity: int = Field(default=0, ge=0)
    default_cost_per_km: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_load_cost: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None
    active: bool = True


class LorryData(AdministrationData):
    registration_or_name: str = Field(min_length=1, max_length=100)
    lorry_type_id: int
    haulier_id: int | None = None
    ownership_type: OwnershipType = OwnershipType.OWNED
    home_location_id: int | None = None
    active: bool = True
    notes: str | None = None


class VanData(AdministrationData):
    registration_or_name: str = Field(min_length=1, max_length=100)
    passenger_capacity: int = Field(default=0, ge=0)
    cargo_capacity_units: Decimal = Field(default=Decimal("0"), ge=0)
    home_location_id: int
    ownership_type: OwnershipType = OwnershipType.OWNED
    cost_per_km: Decimal = Field(default=Decimal("0"), ge=0)
    active: bool = True
    notes: str | None = None


class HaulierData(AdministrationData):
    name: str = Field(min_length=1, max_length=150)
    contact_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=50)
    currency: str = Field(default="GBP", min_length=3, max_length=3)
    default_cost_per_km: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_load_cost: Decimal = Field(default=Decimal("0"), ge=0)
    waiting_hourly_cost: Decimal = Field(default=Decimal("0"), ge=0)
    fuel_surcharge_percent: Decimal = Field(default=Decimal("0"), ge=0)
    active: bool = True
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, value: str) -> str:
        return value.upper()
