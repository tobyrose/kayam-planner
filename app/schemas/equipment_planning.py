from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.equipment_planning import AllocationStrength, AssignmentStatus
from app.models.jobs import RecordSource


class EquipmentAssignmentData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    job_equipment_requirement_id: int
    equipment_asset_id: int
    start_at: datetime
    end_at: datetime
    allocation_strength: AllocationStrength = AllocationStrength.SOFT
    assignment_source: RecordSource = RecordSource.MANUAL
    locked: bool = False
    status: AssignmentStatus = AssignmentStatus.ACTIVE
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("Assignment end must be after its start")
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("Assignment dates must include a timezone")
        return self
