from __future__ import annotations

from app.domain.routing import Coordinates, GeocodingResult, RouteResult, RoutingUnavailableError


class ManualRoutingProvider:
    name = "manual"

    def route(
        self, origin: Coordinates, destination: Coordinates, vehicle_profile: str
    ) -> RouteResult:
        raise RoutingUnavailableError("Enter distance and driving time manually")

    def geocode(self, address: str) -> list[GeocodingResult]:
        return []
