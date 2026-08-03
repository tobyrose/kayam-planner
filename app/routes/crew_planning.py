from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.models.administration import CrewMember, Tentmaster
from app.models.crew_planning import CrewActivityType
from app.routes.jobs import parse_datetime
from app.services.crew_planning import CrewPlanningError, CrewPlanningService
from app.services.roster_board import RosterBoardError, RosterBoardService

router = APIRouter(tags=["crew planning"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


@router.get("/planning/activity/new", response_class=HTMLResponse)
def activity_form(
    request: Request,
    session: SessionDependency,
    tentmaster_id: int | None = None,
    start: str | None = None,
    end: str | None = None,
    board_start: str | None = None,
    board_end: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="planning/activity_form.html",
        context={
            "tentmasters": session.scalars(
                select(Tentmaster).where(Tentmaster.active).order_by(Tentmaster.name)
            ).all(),
            "crew_members": session.scalars(
                select(CrewMember).where(CrewMember.active).order_by(CrewMember.name)
            ).all(),
            "activity_types": CrewActivityType,
            "tentmaster_id": tentmaster_id,
            "start": start,
            "end": end,
            "board_start": board_start or "",
            "board_end": board_end or "",
            "errors": [],
        },
    )


@router.post("/planning/activity/new", response_model=None)
async def create_activity(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    payload = {
        "activity_type": form.get("activity_type"),
        "tentmaster_id": form.get("tentmaster_id") or None,
        "crew_member_id": form.get("crew_member_id") or None,
        "start_at": parse_datetime(form.get("start_at")),
        "end_at": parse_datetime(form.get("end_at")),
        "required_headcount": form.get("required_headcount") or 0,
        "title": form.get("title"),
        "notes": form.get("notes") or None,
        "locked": "locked" in form,
    }
    try:
        CrewPlanningService(session).create_activity(payload)
    except (ValidationError, CrewPlanningError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    board_start = str(form.get("board_start") or "")
    board_end = str(form.get("board_end") or "")
    return RedirectResponse(f"/planning?start={board_start}&end={board_end}", status_code=303)


@router.get("/planning/roster", response_class=HTMLResponse)
def roster_board(
    request: Request,
    session: SessionDependency,
    start: date | None = None,
    days: int | None = None,
    year: int | None = None,
    errors: str | None = None,
) -> HTMLResponse:
    # Default to the current calendar year unless an explicit start/days (the From/Range
    # pickers) or a `year` (the year selector) is given — matches the season board/flow diagram.
    default_year = year or date.today().year
    start_date = start or date(default_year, 1, 1)
    days_count = (
        (date(default_year, 12, 31) - start_date).days + 1 if days is None else days
    )
    days_count = max(7, min(days_count, 366))
    end_date = start_date + timedelta(days=days_count - 1)
    board = RosterBoardService(session).build(start_date, end_date)
    return templates.TemplateResponse(
        request=request,
        name="planning/roster_board.html",
        context={
            "board": board,
            "start_date": start_date,
            "days_count": days_count,
            "errors": [errors] if errors else [],
            "current_year": date.today().year,
        },
    )


@router.post("/planning/roster/move", response_model=None)
async def move_crew_member(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    start = form.get("board_start") or ""
    try:
        crew_member_id = int(str(form.get("crew_member_id")))
        raw_tentmaster_id = form.get("to_tentmaster_id")
        to_tentmaster_id = int(str(raw_tentmaster_id)) if raw_tentmaster_id else None
        effective_date = date.fromisoformat(str(form.get("effective_date")))
        RosterBoardService(session).move_crew_member(
            crew_member_id, to_tentmaster_id, effective_date
        )
    except (RosterBoardError, ValueError) as error:
        return RedirectResponse(
            f"/planning/roster?start={start}&errors={quote(str(error))}", status_code=303
        )
    return RedirectResponse(f"/planning/roster?start={start}", status_code=303)
