from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.models.administration import CrewMember, Tentmaster
from app.models.crew_planning import CrewActivityType
from app.models.jobs import JobPhase, RecordSource
from app.routes.jobs import parse_datetime
from app.services.crew_planning import CrewPlanningError, CrewPlanningService

router = APIRouter(tags=["crew planning"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


@router.get("/planning/crew", response_class=HTMLResponse)
def crew_board(
    request: Request,
    session: SessionDependency,
    start: date | None = None,
    days: int = 31,
) -> HTMLResponse:
    start_date = start or date.today().replace(day=1)
    days = max(7, min(days, 366))
    end_date = start_date + timedelta(days=days - 1)
    service = CrewPlanningService(session)
    board = service.board_data(start_date, end_date)
    totals = service.daily_totals(start_date, end_date, get_settings().default_timezone)
    return templates.TemplateResponse(
        request=request,
        name="planning/crew_board.html",
        context={
            **board,
            "start_date": start_date,
            "end_date": end_date,
            "days_count": days,
            "totals": totals,
        },
    )


def assignment_context(
    request: Request, session: Session, phase: JobPhase, errors: list[str] | None = None
) -> dict[str, Any]:
    return {
        "request": request,
        "phase": phase,
        "crew_members": session.scalars(
            select(CrewMember).where(CrewMember.active).order_by(CrewMember.name)
        ).all(),
        "tentmasters": session.scalars(
            select(Tentmaster).where(Tentmaster.active).order_by(Tentmaster.name)
        ).all(),
        "errors": errors or [],
    }


@router.get("/jobs/{job_id}/phases/{phase_id}/crew/new", response_class=HTMLResponse)
def assignment_form(
    request: Request, job_id: int, phase_id: int, session: SessionDependency
) -> HTMLResponse:
    phase = session.get(JobPhase, phase_id)
    if phase is None or phase.job_id != job_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    return templates.TemplateResponse(
        request=request,
        name="planning/crew_assignment_form.html",
        context=assignment_context(request, session, phase),
    )


@router.post("/jobs/{job_id}/phases/{phase_id}/crew/new", response_model=None)
async def create_assignment(
    request: Request, job_id: int, phase_id: int, session: SessionDependency
) -> Response:
    phase = session.get(JobPhase, phase_id)
    if phase is None or phase.job_id != job_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    form = await request.form()
    payload = {
        "job_phase_id": phase_id,
        "crew_member_id": form.get("crew_member_id") or None,
        "placeholder_name": form.get("placeholder_name") or None,
        "tentmaster_id": form.get("tentmaster_id") or phase.tentmaster_id,
        "start_at": parse_datetime(form.get("start_at")),
        "end_at": parse_datetime(form.get("end_at")),
        "role": form.get("role") or "Crew",
        "assignment_source": RecordSource.MANUAL.value,
        "locked": "locked" in form,
        "hourly_cost_override": form.get("hourly_cost_override") or None,
        "notes": form.get("notes") or None,
    }
    try:
        CrewPlanningService(session).assign(payload)
    except (ValidationError, CrewPlanningError) as error:
        return templates.TemplateResponse(
            request=request,
            name="planning/crew_assignment_form.html",
            context=assignment_context(request, session, phase, [str(error)]),
            status_code=422,
        )
    return RedirectResponse(f"/jobs/{job_id}#phases", status_code=303)


@router.get("/planning/crew/activity/new", response_class=HTMLResponse)
def activity_form(
    request: Request,
    session: SessionDependency,
    tentmaster_id: int | None = None,
    start: str | None = None,
    end: str | None = None,
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
            "errors": [],
        },
    )


@router.post("/planning/crew/activity/new", response_model=None)
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
    start_at = payload["start_at"]
    start_date = start_at.date().isoformat() if isinstance(start_at, datetime) else ""
    return RedirectResponse(f"/planning/crew?start={start_date}", status_code=303)
