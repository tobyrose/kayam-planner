from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import Location
from app.services.routing import RoutingService, margin_status, route_cache_key


def test_cache_key_is_stable_and_directional() -> None:
    assert route_cache_key(1, 2, " HGV ") == route_cache_key(1, 2, "hgv")
    assert route_cache_key(1, 2, "hgv") != route_cache_key(2, 1, "hgv")


def test_manual_route_is_cached(session: Session) -> None:
    seed_development_data(session)
    locations = session.scalars(select(Location).order_by(Location.id)).all()
    service = RoutingService(session)
    result = service.enter_manual(locations[0], locations[1], Decimal("123.4"), 150)
    cached = service.route(locations[0], locations[1])
    assert cached == result
    service.confirm_geocode(locations[0], Decimal("51.752"), Decimal("-1.258"))
    assert locations[0].geocoded_at is not None


def test_transition_feasibility_and_receiving_warning(session: Session) -> None:
    service = RoutingService(session)
    start = datetime(2026, 5, 1, 8, tzinfo=UTC)
    feasible = service.feasibility(
        start,
        start + timedelta(hours=36),
        240,
        receiving_crew_available_at=start + timedelta(hours=35),
    )
    assert feasible.status == "green"
    assert feasible.receiving_warning is False

    infeasible = service.feasibility(start, start + timedelta(hours=3), 240)
    assert infeasible.status == "red"
    assert infeasible.receiving_warning is True


def test_margin_status_thresholds() -> None:
    assert margin_status(359) == "red"
    assert margin_status(360) == "amber"
    assert margin_status(1440) == "green"
