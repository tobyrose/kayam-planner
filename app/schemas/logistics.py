from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.jobs import RecordSource
from app.models.logistics import EstimateSource, LoadStatus, MovementStatus


class MovementData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    movement_code: str = Field(min_length=1, max_length=50)
    origin_location_id: int
    destination_location_id: int
    depart_after: datetime
    arrive_by: datetime
    loading_minutes: int = Field(default=60, ge=0)
    unloading_minutes: int = Field(default=60, ge=0)
    contingency_minutes: int = Field(default=0, ge=0)
    status: MovementStatus = MovementStatus.REQUIRED
    source: RecordSource = RecordSource.MANUAL
    locked: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def validate_movement(self) -> MovementData:
        if self.origin_location_id == self.destination_location_id:
            raise ValueError("Origin and destination must differ")
        if self.arrive_by <= self.depart_after:
            raise ValueError("Arrival must be after departure")
        return self


class LoadData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equipment_movement_id: int
    load_number: int = Field(gt=0)
    lorry_id: int | None = None
    lorry_type_id: int
    status: LoadStatus = LoadStatus.DRAFT
    planned_departure_at: datetime | None = None
    planned_arrival_at: datetime | None = None
    estimated_distance_km: Decimal = Field(default=Decimal(0), ge=0)
    estimated_cost: Decimal = Field(default=Decimal(0), ge=0)
    estimate_source: EstimateSource = EstimateSource.CALCULATED
    locked: bool = False
    notes: str | None = None


class LoadItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    load_id: int
    equipment_asset_id: int | None = None
    equipment_type_id: int | None = None
    quantity: int = Field(default=1, gt=0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_item(self) -> LoadItemData:
        if (self.equipment_asset_id is None) == (self.equipment_type_id is None):
            raise ValueError("Choose either one asset or one equipment type")
        if self.equipment_asset_id is not None and self.quantity != 1:
            raise ValueError("An individual asset has quantity 1")
        return self
