from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.models.administration import CrewMember, Location, Tentmaster, Van
from app.models.crew_movements import CrewMovement, JourneyMode
from app.services.crew_movements import (
    CrewMovementError,
    CrewMovementService,
    active_transfer_label,
)

router = APIRouter(tags=["crew movements"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _datetime(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    return (
        parsed
        if parsed.tzinfo
        else parsed.replace(tzinfo=ZoneInfo(get_settings().default_timezone))
    )


@router.get("/crew-moves", response_class=HTMLResponse)
def list_moves(request: Request, session: SessionDependency) -> HTMLResponse:
    moves = session.scalars(select(CrewMovement).order_by(CrewMovement.depart_after)).all()
    return templates.TemplateResponse(
        request=request, name="crew_movements/list.html", context={"movements": moves}
    )


@router.get("/crew-moves/export.csv", response_class=PlainTextResponse)
def export_moves(session: SessionDependency) -> PlainTextResponse:
    return PlainTextResponse(
        CrewMovementService(session).export_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="crew-moves.csv"'},
    )


@router.get("/crew-moves/new", response_class=HTMLResponse)
def new_move(request: Request, session: SessionDependency) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="crew_movements/form.html",
        context={
            "locations": session.scalars(select(Location).order_by(Location.name)).all(),
            "vans": session.scalars(
                select(Van).where(Van.active).order_by(Van.registration_or_name)
            ).all(),
            "tentmasters": session.scalars(select(Tentmaster).order_by(Tentmaster.name)).all(),
        },
    )


@router.post("/crew-moves/new", response_model=None)
async def create_move(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    movement = CrewMovementService(session).create(
        {
            "movement_code": form.get("movement_code"),
            "origin_location_id": form.get("origin_location_id"),
            "destination_location_id": form.get("destination_location_id"),
            "tentmaster_id": form.get("tentmaster_id") or None,
            "van_id": form.get("van_id") or None,
            "depart_after": _datetime(form.get("depart_after")),
            "arrive_by": _datetime(form.get("arrive_by")),
            "notes": form.get("notes") or None,
        }
    )
    return RedirectResponse(f"/crew-moves/{movement.id}", status_code=303)


@router.get("/crew-moves/{movement_id}", response_class=HTMLResponse)
def move_detail(request: Request, movement_id: int, session: SessionDependency) -> HTMLResponse:
    movement = session.get(CrewMovement, movement_id)
    if movement is None:
        raise HTTPException(status_code=404, detail="Crew movement not found")
    return templates.TemplateResponse(
        request=request,
        name="crew_movements/detail.html",
        context={
            "movement": movement,
            "crew": session.scalars(
                select(CrewMember).where(CrewMember.active).order_by(CrewMember.name)
            ).all(),
            "tentmasters": session.scalars(select(Tentmaster).order_by(Tentmaster.name)).all(),
            "journey_modes": JourneyMode,
            "transfer_label": active_transfer_label,
        },
    )


@router.post("/crew-moves/{movement_id}/passengers", response_model=None)
async def add_passenger(request: Request, movement_id: int, session: SessionDependency) -> Response:
    form = await request.form()
    try:
        CrewMovementService(session).add_passenger(
            movement_id,
            crew_member_id=int(str(form["crew_member_id"])) if form.get("crew_member_id") else None,
            placeholder_label=str(form.get("placeholder_label") or "") or None,
            quantity=int(str(form.get("quantity") or 1)),
            joining_tentmaster_id=(
                int(str(form["joining_tentmaster_id"]))
                if form.get("joining_tentmaster_id")
                else None
            ),
            leaving_tentmaster_id=(
                int(str(form["leaving_tentmaster_id"]))
                if form.get("leaving_tentmaster_id")
                else None
            ),
        )
    except CrewMovementError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return RedirectResponse(f"/crew-moves/{movement_id}", status_code=303)


@router.post("/crew-moves/{movement_id}/legs", response_model=None)
async def add_leg(request: Request, movement_id: int, session: SessionDependency) -> Response:
    form = await request.form()
    CrewMovementService(session).add_leg(
        movement_id,
        {
            "sequence": int(str(form.get("sequence"))),
            "mode": JourneyMode(str(form.get("mode"))),
            "origin_label": str(form.get("origin_label")),
            "destination_label": str(form.get("destination_label")),
            "depart_at": _datetime(form.get("depart_at")),
            "arrive_at": _datetime(form.get("arrive_at")),
            "booking_reference": str(form.get("booking_reference") or "") or None,
        },
    )
    return RedirectResponse(f"/crew-moves/{movement_id}", status_code=303)
