from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.jobs import CommercialStatus, PhaseType, PlanningStatus, RecordSource


class JobData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    job_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    customer_name: str = Field(min_length=1, max_length=200)
    location_id: int
    commercial_status: CommercialStatus = CommercialStatus.ENQUIRY
    planning_status: PlanningStatus = PlanningStatus.NOT_PLANNED
    confidence_percent: int | None = Field(default=None, ge=0, le=100)
    contract_revenue: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="GBP", min_length=3, max_length=3)
    site_access_at: datetime
    must_be_up_at: datetime
    show_start_at: datetime | None = None
    show_end_at: datetime | None = None
    strike_available_at: datetime
    site_clear_by: datetime | None = None
    maintenance_cover_required: bool = False
    catering_arrangement: str | None = None
    accommodation_arrangement: str | None = None
    ground_type: str | None = Field(default=None, max_length=100)
    local_crew_supplied: int = Field(default=0, ge=0)
    local_crew_required: int = Field(default=0, ge=0)
    build_scope: str | None = None
    strike_scope: str | None = None
    operational_notes: str | None = None
    commercial_notes: str | None = None
    deposit_received_at: datetime | None = None

    @model_validator(mode="after")
    def validate_milestones(self) -> Self:
        if self.site_access_at > self.must_be_up_at:
            raise ValueError("Site access must be before the must-be-up milestone")
        if self.must_be_up_at > self.strike_available_at:
            raise ValueError("Strike availability must be after the must-be-up milestone")
        if self.show_start_at and self.show_end_at and self.show_start_at > self.show_end_at:
            raise ValueError("Show start must be before show end")
        if self.site_clear_by and self.strike_available_at > self.site_clear_by:
            raise ValueError("Site-clear deadline must be after strike availability")
        for name in (
            "site_access_at",
            "must_be_up_at",
            "show_start_at",
            "show_end_at",
            "strike_available_at",
            "site_clear_by",
            "deposit_received_at",
        ):
            value = getattr(self, name)
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name.replace('_', ' ').title()} must include a timezone")
        return self


class JobTentRequirementData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tent_configuration_id: int
    quantity: int = Field(gt=0)
    custom_name: str | None = Field(default=None, max_length=200)
    build_start_override: datetime | None = None
    build_duration_override_hours: Decimal | None = Field(default=None, gt=0)
    strike_duration_override_hours: Decimal | None = Field(default=None, gt=0)
    required_crew_override: int | None = Field(default=None, ge=0)
    notes: str | None = None


class JobPhaseData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    phase_type: PhaseType
    tentmaster_id: int | None = None
    start_at: datetime
    end_at: datetime
    required_headcount: int = Field(default=0, ge=0)
    notes: str | None = None
    locked: bool = False
    source: RecordSource = RecordSource.MANUAL

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("Phase end must be after phase start")
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("Phase dates must include a timezone")
        return self
