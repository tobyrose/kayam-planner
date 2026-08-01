from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class RoutingUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class Coordinates:
    latitude: Decimal
    longitude: Decimal


@dataclass(frozen=True)
class RouteResult:
    distance_km: Decimal
    driving_duration_minutes: int
    provider: str


@dataclass(frozen=True)
class GeocodingResult:
    label: str
    coordinates: Coordinates
    place_id: str | None = None


class RoutingProvider(Protocol):
    name: str

    def route(
        self, origin: Coordinates, destination: Coordinates, vehicle_profile: str
    ) -> RouteResult: ...

    def geocode(self, address: str) -> list[GeocodingResult]: ...
