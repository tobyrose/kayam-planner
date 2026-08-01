from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.models.administration import Location
from app.models.logistics import RouteCache
from app.services.routing import RoutingService

router = APIRouter(tags=["routing"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


@router.get("/routes", response_class=HTMLResponse)
def routes_page(request: Request, session: SessionDependency) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="routing/index.html",
        context={
            "locations": session.scalars(select(Location).order_by(Location.name)).all(),
            "routes": session.scalars(
                select(RouteCache).order_by(RouteCache.calculated_at.desc())
            ).all(),
        },
    )


@router.post("/routes/manual", response_model=None)
async def manual_route(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    origin = session.get(Location, int(str(form.get("origin_location_id"))))
    destination = session.get(Location, int(str(form.get("destination_location_id"))))
    if origin is None or destination is None or origin.id == destination.id:
        raise HTTPException(status_code=422, detail="Choose two different locations")
    RoutingService(session).enter_manual(
        origin,
        destination,
        Decimal(str(form.get("distance_km"))),
        int(str(form.get("driving_minutes"))),
        str(form.get("vehicle_profile") or "hgv"),
    )
    return RedirectResponse("/routes", status_code=303)


@router.post("/routes/confirm-geocode", response_model=None)
async def confirm_geocode(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    location = session.get(Location, int(str(form.get("location_id"))))
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    try:
        RoutingService(session).confirm_geocode(
            location,
            Decimal(str(form.get("latitude"))),
            Decimal(str(form.get("longitude"))),
            provider=str(form.get("provider") or "manual"),
            place_id=str(form.get("place_id") or "") or None,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse("/routes", status_code=303)
