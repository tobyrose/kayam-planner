from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.crew_planning import CrewActivityType


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
