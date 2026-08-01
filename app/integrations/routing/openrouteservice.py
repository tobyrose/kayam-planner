from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.domain.routing import (
    Coordinates,
    GeocodingResult,
    RouteResult,
    RoutingUnavailableError,
)


class OpenRouteServiceProvider:
    name = "openrouteservice"

    def __init__(self, api_key: str | None) -> None:
        if not api_key:
            raise RoutingUnavailableError(
                "OpenRouteService API key is not configured; manual routing remains available"
            )
        self.api_key = api_key

    def route(
        self, origin: Coordinates, destination: Coordinates, vehicle_profile: str
    ) -> RouteResult:
        profile = "driving-hgv" if vehicle_profile == "hgv" else "driving-car"
        url = f"https://api.openrouteservice.org/v2/directions/{profile}/json"
        body = json.dumps(
            {
                "coordinates": [
                    [float(origin.longitude), float(origin.latitude)],
                    [float(destination.longitude), float(destination.latitude)],
                ]
            }
        ).encode()
        data = self._request(Request(url, data=body, method="POST"))
        summary = data["routes"][0]["summary"]
        return RouteResult(
            distance_km=(Decimal(str(summary["distance"])) / 1000).quantize(Decimal("0.01")),
            driving_duration_minutes=round(summary["duration"] / 60),
            provider=self.name,
        )

    def geocode(self, address: str) -> list[GeocodingResult]:
        query = urlencode({"api_key": self.api_key, "text": address, "size": 5})
        data = self._request(
            Request(f"https://api.openrouteservice.org/geocode/search?{query}", method="GET")
        )
        return [
            GeocodingResult(
                feature["properties"]["label"],
                Coordinates(
                    Decimal(str(feature["geometry"]["coordinates"][1])),
                    Decimal(str(feature["geometry"]["coordinates"][0])),
                ),
                feature["properties"].get("id"),
            )
            for feature in data.get("features", [])
        ]

    def _request(self, request: Request) -> dict[str, Any]:
        request.add_header("Authorization", self.api_key)
        request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310
                result: dict[str, Any] = json.loads(response.read())
                return result
        except (URLError, TimeoutError, KeyError, ValueError) as error:
            raise RoutingUnavailableError(f"Routing provider failed: {error}") from error
