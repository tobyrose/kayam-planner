from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.jobs import CommercialStatus, PhaseType, PlanningStatus, RecordSource


class JobData(BaseModel):
    """Contract Up/Down dates are entered per tent (`JobTentRequirementData`), not here — a job
    starts with only general, optional site-availability dates until at least one tent is added.
    """

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
    site_access_at: datetime | None = None
    site_clear_by: datetime | None = None
    maintenance_cover_required: bool = False
    catering_arrangement: str | None = None
    accommodation_arrangement: str | None = None
    ground_type: str | None = Field(default=None, max_length=100)
    build_scope: str | None = None
    strike_scope: str | None = None
    operational_notes: str | None = None
    commercial_notes: str | None = None
    deposit_received_at: datetime | None = None

    @model_validator(mode="after")
    def validate_milestones(self) -> Self:
        if self.site_access_at and self.site_clear_by and self.site_access_at > self.site_clear_by:
            raise ValueError("Site access must be before site clear")
        for name in ("site_access_at", "site_clear_by", "deposit_received_at"):
            value = getattr(self, name)
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name.replace('_', ' ').title()} must include a timezone")
        return self


class JobTentRequirementData(BaseModel):
    """`sequence` is a hyphen-delimited section-code sequence, e.g. "K-M-M-M-K" — matching the
    notation already used in the business's own load-content lists — parsed by
    `JobService.add_tent_requirement` into ordered `JobTentSection` rows.

    `contracted_up_at`/`contracted_down_at` are fixed once set (see `JobPhase` docstring) and
    drive the tent's auto-seeded Up phase plus the job's auto-seeded Build/Break phases.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sequence: str = Field(min_length=1, max_length=500)
    quantity: int = Field(gt=0)
    custom_name: str | None = Field(default=None, max_length=200)
    contracted_up_at: datetime
    contracted_down_at: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.contracted_down_at <= self.contracted_up_at:
            raise ValueError("Contract down must be after contract up")
        if self.contracted_up_at.tzinfo is None or self.contracted_down_at.tzinfo is None:
            raise ValueError("Contract dates must include a timezone")
        return self


class JobPhaseData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    phase_type: PhaseType
    job_tent_requirement_id: int | None = None
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
        if (self.phase_type == PhaseType.UP) != (self.job_tent_requirement_id is not None):
            raise ValueError("An Up phase must reference a tent; other phases must not")
        return self


class LocalCrewBookingData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    headcount: int = Field(gt=0)
    start_at: datetime
    end_at: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("Booking end must be after booking start")
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("Booking dates must include a timezone")
        return self
