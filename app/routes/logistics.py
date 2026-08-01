from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.models.administration import EquipmentAsset, EquipmentType, Location, LorryType
from app.models.logistics import EquipmentMovement, Load, LoadStatus, MovementStatus
from app.services.costing import CostingError, CostingService
from app.services.logistics import LogisticsError, LogisticsService

router = APIRouter(tags=["logistics"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _datetime(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    return (
        parsed
        if parsed.tzinfo
        else parsed.replace(tzinfo=ZoneInfo(get_settings().default_timezone))
    )


@router.get("/loads", response_class=HTMLResponse)
def loads_list(request: Request, session: SessionDependency) -> HTMLResponse:
    loads = session.scalars(
        select(Load).join(Load.movement).order_by(EquipmentMovement.depart_after)
    ).all()
    service = LogisticsService(session)
    return templates.TemplateResponse(
        request=request,
        name="logistics/list.html",
        context={"loads": loads, "capacities": {load.id: service.capacity(load) for load in loads}},
    )


@router.get("/loads/export.csv", response_class=PlainTextResponse)
def loads_export(session: SessionDependency) -> PlainTextResponse:
    return PlainTextResponse(
        LogisticsService(session).export_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="loads.csv"'},
    )


@router.get("/loads/new", response_class=HTMLResponse)
def movement_form(request: Request, session: SessionDependency) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="logistics/movement_form.html",
        context={
            "locations": session.scalars(select(Location).order_by(Location.name)).all(),
            "lorry_types": session.scalars(select(LorryType).order_by(LorryType.name)).all(),
            "movement_statuses": MovementStatus,
        },
    )


@router.post("/loads/new", response_model=None)
async def create_movement(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    service = LogisticsService(session)
    try:
        movement = service.create_movement(
            {
                "movement_code": form.get("movement_code"),
                "origin_location_id": form.get("origin_location_id"),
                "destination_location_id": form.get("destination_location_id"),
                "depart_after": _datetime(form.get("depart_after")),
                "arrive_by": _datetime(form.get("arrive_by")),
                "status": form.get("status", "required"),
            }
        )
        load = service.create_load(
            {
                "equipment_movement_id": movement.id,
                "load_number": form.get("load_number", 1),
                "lorry_type_id": form.get("lorry_type_id"),
                "planned_departure_at": movement.depart_after,
                "planned_arrival_at": movement.arrive_by,
            }
        )
    except (ValidationError, LogisticsError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse(f"/loads/{load.id}", status_code=303)


@router.get("/loads/{load_id}", response_class=HTMLResponse)
def load_detail(request: Request, load_id: int, session: SessionDependency) -> HTMLResponse:
    load = session.get(Load, load_id)
    if load is None:
        raise HTTPException(status_code=404, detail="Load not found")
    return templates.TemplateResponse(
        request=request,
        name="logistics/detail.html",
        context={
            "load": load,
            "capacity": LogisticsService(session).capacity(load),
            "assets": session.scalars(
                select(EquipmentAsset).order_by(EquipmentAsset.asset_code)
            ).all(),
            "equipment_types": session.scalars(
                select(EquipmentType).order_by(EquipmentType.code)
            ).all(),
            "load_statuses": LoadStatus,
        },
    )


@router.post("/loads/{load_id}/items", response_model=None)
async def add_load_item(request: Request, load_id: int, session: SessionDependency) -> Response:
    form = await request.form()
    try:
        LogisticsService(session).add_item(
            {
                "load_id": load_id,
                "equipment_asset_id": form.get("equipment_asset_id") or None,
                "equipment_type_id": form.get("equipment_type_id") or None,
                "quantity": form.get("quantity") or 1,
                "notes": form.get("notes") or None,
            }
        )
    except (ValidationError, LogisticsError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return RedirectResponse(f"/loads/{load_id}", status_code=303)


@router.post("/loads/{load_id}/status", response_model=None)
async def update_load_status(
    request: Request, load_id: int, session: SessionDependency
) -> Response:
    form = await request.form()
    try:
        LogisticsService(session).set_status(load_id, str(form.get("status")))
    except LogisticsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return RedirectResponse(f"/loads/{load_id}", status_code=303)


@router.post("/loads/{load_id}/estimate", response_model=None)
async def update_load_estimate(
    request: Request, load_id: int, session: SessionDependency
) -> Response:
    load = session.get(Load, load_id)
    if load is None:
        raise HTTPException(status_code=404, detail="Load not found")
    form = await request.form()
    try:
        CostingService(session).set_manual_load_estimate(
            load, Decimal(str(form.get("estimated_cost")))
        )
    except CostingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse(f"/loads/{load_id}", status_code=303)
