from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.routing import Coordinates, RouteResult, RoutingProvider, RoutingUnavailableError
from app.integrations.routing.manual import ManualRoutingProvider
from app.integrations.routing.openrouteservice import OpenRouteServiceProvider
from app.models.administration import Location
from app.models.logistics import RouteCache


@dataclass(frozen=True)
class FeasibilityResult:
    available_minutes: int
    required_minutes: int
    margin_minutes: int
    status: str
    receiving_warning: bool


def route_cache_key(origin_id: int, destination_id: int, vehicle_profile: str) -> str:
    raw = f"v1:{origin_id}:{destination_id}:{vehicle_profile.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def margin_status(margin_minutes: int) -> str:
    settings = get_settings()
    if margin_minutes < settings.route_amber_margin_minutes:
        return "red"
    if margin_minutes < settings.route_green_margin_minutes:
        return "amber"
    return "green"


class RoutingService:
    def __init__(self, session: Session, provider: RoutingProvider | None = None) -> None:
        self.session = session
        self.provider = provider or self._configured_provider()

    def _configured_provider(self) -> RoutingProvider:
        settings = get_settings()
        if settings.routing_provider == "openrouteservice":
            return OpenRouteServiceProvider(settings.openrouteservice_api_key)
        return ManualRoutingProvider()

    def route(self, origin: Location, destination: Location, profile: str = "hgv") -> RouteResult:
        key = route_cache_key(origin.id, destination.id, profile)
        cached = self.session.scalar(select(RouteCache).where(RouteCache.cache_key == key))
        if cached is not None:
            return RouteResult(cached.distance_km, cached.driving_duration_minutes, cached.provider)
        if None in (origin.latitude, origin.longitude, destination.latitude, destination.longitude):
            raise RoutingUnavailableError("Both locations need confirmed coordinates")
        result = self.provider.route(
            Coordinates(origin.latitude, origin.longitude),  # type: ignore[arg-type]
            Coordinates(destination.latitude, destination.longitude),  # type: ignore[arg-type]
            profile,
        )
        self._store(origin, destination, profile, result, manual=False)
        return result

    def enter_manual(
        self,
        origin: Location,
        destination: Location,
        distance_km: Decimal,
        driving_minutes: int,
        profile: str = "hgv",
    ) -> RouteResult:
        result = RouteResult(distance_km, driving_minutes, "manual")
        self._store(origin, destination, profile, result, manual=True)
        return result

    def confirm_geocode(
        self,
        location: Location,
        latitude: Decimal,
        longitude: Decimal,
        *,
        provider: str = "manual",
        place_id: str | None = None,
    ) -> Location:
        if not (Decimal("-90") <= latitude <= Decimal("90")):
            raise ValueError("Latitude must be between -90 and 90")
        if not (Decimal("-180") <= longitude <= Decimal("180")):
            raise ValueError("Longitude must be between -180 and 180")
        location.latitude = latitude
        location.longitude = longitude
        location.geocoding_provider = provider
        location.geocoding_place_id = place_id
        location.geocoded_at = datetime.now(UTC)
        self.session.commit()
        return location

    def _store(
        self,
        origin: Location,
        destination: Location,
        profile: str,
        result: RouteResult,
        *,
        manual: bool,
    ) -> None:
        key = route_cache_key(origin.id, destination.id, profile)
        cache = self.session.scalar(select(RouteCache).where(RouteCache.cache_key == key))
        if cache is None:
            cache = RouteCache(
                cache_key=key,
                origin_location_id=origin.id,
                destination_location_id=destination.id,
                vehicle_profile=profile,
                provider=result.provider,
                distance_km=result.distance_km,
                driving_duration_minutes=result.driving_duration_minutes,
                calculated_at=datetime.now(UTC),
                manual=manual,
            )
            self.session.add(cache)
        else:
            cache.provider = result.provider
            cache.distance_km = result.distance_km
            cache.driving_duration_minutes = result.driving_duration_minutes
            cache.calculated_at = datetime.now(UTC)
            cache.manual = manual
        self.session.commit()

    def operational_minutes(
        self,
        driving_minutes: int,
        loading_minutes: int = 60,
        unloading_minutes: int = 60,
        contingency_minutes: int = 0,
    ) -> int:
        return driving_minutes + loading_minutes + unloading_minutes + contingency_minutes

    def feasibility(
        self,
        released_at: datetime,
        required_at: datetime,
        driving_minutes: int,
        *,
        loading_minutes: int = 60,
        unloading_minutes: int = 60,
        contingency_minutes: int = 0,
        receiving_crew_available_at: datetime | None = None,
    ) -> FeasibilityResult:
        required = self.operational_minutes(
            driving_minutes, loading_minutes, unloading_minutes, contingency_minutes
        )
        available = round((required_at - released_at) / timedelta(minutes=1))
        margin = available - required
        receiving_warning = (
            receiving_crew_available_at is None or receiving_crew_available_at > required_at
        )
        return FeasibilityResult(
            available, required, margin, margin_status(margin), receiving_warning
        )
