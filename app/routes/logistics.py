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
from app.models.jobs import Job
from app.models.logistics import EquipmentMovement, Load, LoadStatus, MovementStatus
from app.services.costing import CostingError, CostingService
from app.services.logistics import LogisticsError, LogisticsService
from app.services.season_plan import SeasonPlanService

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


def _combine_date_time(date_value: Any, time_value: Any) -> datetime:
    """Build a wall-clock datetime from separate HTML date + time inputs."""
    date_part = str(date_value or "").strip()
    time_part = str(time_value or "").strip()
    if not date_part or not time_part:
        raise ValueError("Date and time are both required")
    # time inputs may be HH:MM or HH:MM:SS
    if len(time_part) == 5:
        time_part = f"{time_part}:00"
    return _datetime(f"{date_part}T{time_part}")


@router.get("/loads", response_class=HTMLResponse)
def loads_list(request: Request, session: SessionDependency) -> HTMLResponse:
    loads = session.scalars(
        select(Load).join(Load.movement).order_by(EquipmentMovement.depart_after)
    ).all()
    service = LogisticsService(session)
    return templates.TemplateResponse(
        request=request,
        name="logistics/list.html",
        context={
            "loads": loads,
            "capacities": {load.id: service.capacity(load) for load in loads},
            "plan_message": request.query_params.get("plan"),
        },
    )


@router.post("/loads/generate-season", response_model=None)
def generate_season_plan(session: SessionDependency) -> Response:
    """Replace unlocked auto-generated loads/crew moves with a whole-season plan."""
    result = SeasonPlanService(session).generate(include_crew_moves=True)
    from urllib.parse import quote

    return RedirectResponse(
        f"/loads?plan={quote(result.summary())}",
        status_code=303,
    )


@router.get("/loads/export.csv", response_class=PlainTextResponse)
def loads_export(session: SessionDependency) -> PlainTextResponse:
    return PlainTextResponse(
        LogisticsService(session).export_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="loads.csv"'},
    )


def _location_options_with_jobs(session: Session) -> list[tuple[int, str]]:
    """Location select labels: venue name plus job code(s) at that site when known."""
    locations = session.scalars(select(Location).order_by(Location.name)).all()
    jobs = session.scalars(select(Job).order_by(Job.job_code)).all()
    jobs_by_location: dict[int, list[str]] = {}
    for job in jobs:
        jobs_by_location.setdefault(job.location_id, []).append(job.job_code)
    options: list[tuple[int, str]] = []
    for location in locations:
        job_codes = jobs_by_location.get(location.id, [])
        if job_codes:
            options.append((location.id, f"{location.name} — {', '.join(job_codes)}"))
        else:
            options.append((location.id, location.name))
    return options


def _lorry_types_for_form(session: Session) -> list[LorryType]:
    """Active operational types only — Curtain/Flat; hide legacy demo 'Standard artic'."""
    return list(
        session.scalars(
            select(LorryType)
            .where(LorryType.active.is_(True), LorryType.name != "Standard artic")
            .order_by(LorryType.name)
        ).all()
    )


def _movement_form_context(
    request: Request,
    session: Session,
    *,
    values: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    service = LogisticsService(session)
    return {
        "request": request,
        "location_options": _location_options_with_jobs(session),
        "lorry_types": _lorry_types_for_form(session),
        "movement_statuses": MovementStatus,
        "next_load_number": service.next_load_number(),
        "values": values or {},
        "errors": errors or [],
    }


@router.get("/loads/new", response_class=HTMLResponse)
def movement_form(request: Request, session: SessionDependency) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="logistics/movement_form.html",
        context=_movement_form_context(request, session),
    )


@router.post("/loads/new", response_model=None)
async def create_movement(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    values = {key: str(form.get(key) or "") for key in form.keys()}
    service = LogisticsService(session)
    try:
        depart_after = _combine_date_time(
            form.get("depart_after_date"), form.get("depart_after_time")
        )
        arrive_by = _combine_date_time(form.get("arrive_by_date"), form.get("arrive_by_time"))
        movement = service.create_movement(
            {
                # movement_code auto-generated when omitted
                "origin_location_id": form.get("origin_location_id"),
                "destination_location_id": form.get("destination_location_id"),
                "depart_after": depart_after,
                "arrive_by": arrive_by,
                "status": form.get("status", "required"),
            }
        )
        load = service.create_load(
            {
                "equipment_movement_id": movement.id,
                # load_number auto-incremented when omitted
                "lorry_type_id": form.get("lorry_type_id"),
                "planned_departure_at": movement.depart_after,
                "planned_arrival_at": movement.arrive_by,
            }
        )
    except (ValidationError, LogisticsError, ValueError) as error:
        messages = (
            [str(error)]
            if not isinstance(error, ValidationError)
            else [e.get("msg", str(e)) for e in error.errors()]
        )
        return templates.TemplateResponse(
            request=request,
            name="logistics/movement_form.html",
            context=_movement_form_context(
                request, session, values=values, errors=messages
            ),
            status_code=422,
        )
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
