from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.crew_planning import CrewActivityType
from app.models.jobs import RecordSource


class CrewAssignmentData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    job_phase_id: int
    crew_member_id: int | None = None
    placeholder_name: str | None = Field(default=None, max_length=150)
    tentmaster_id: int | None = None
    start_at: datetime
    end_at: datetime
    role: str = Field(default="Crew", min_length=1, max_length=100)
    assignment_source: RecordSource = RecordSource.MANUAL
    locked: bool = False
    hourly_cost_override: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_assignment(self) -> Self:
        if (self.crew_member_id is None) == (self.placeholder_name is None):
            raise ValueError("Choose either one crew member or one placeholder")
        if self.end_at <= self.start_at:
            raise ValueError("Assignment end must be after its start")
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("Assignment dates must include a timezone")
        return self


class CrewActivityData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    activity_type: CrewActivityType
    tentmaster_id: int | None = None
    crew_member_id: int | None = None
    start_at: datetime
    end_at: datetime
    required_headcount: int = Field(default=0, ge=0)
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    locked: bool = False

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("Activity end must be after its start")
        return self
