from __future__ import annotations

from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.services.board import BoardService
from app.services.flow import FlowService
from app.services.jobs import JobError, JobService

router = APIRouter(tags=["seasonal planning"])
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _range(start: date | None, end: date | None, year: int | None) -> tuple[date, date]:
    """Default to the current calendar year unless an explicit start/end (the From/To pickers)
    or a `year` (the year selector) is given — an explicit start/end always wins over `year`,
    since it's more specific and the two controls are never submitted together from the UI."""
    today = date.today()
    default_start = date(year or today.year, 1, 1)
    default_end = date(year or today.year, 12, 31)
    return start or default_start, end or default_end


@router.get("/planning", response_class=HTMLResponse, include_in_schema=False)
def combined_board(
    request: Request,
    session: SessionDependency,
    start: date | None = None,
    end: date | None = None,
    year: int | None = None,
    errors: str | None = None,
) -> HTMLResponse:
    selected_start, selected_end = _range(start, end, year)
    try:
        board = BoardService(session).build(selected_start, selected_end)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return templates.TemplateResponse(
        request=request,
        name="planning/combined_board.html",
        context={
            "board": board,
            "errors": [errors] if errors else [],
            "current_year": date.today().year,
        },
    )


@router.post("/planning/move-phase", response_model=None)
async def move_phase(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    board_start = form.get("board_start") or ""
    board_end = form.get("board_end") or ""
    suffix = f"start={board_start}&end={board_end}"
    try:
        phase_id = int(str(form.get("phase_id")))
        raw_tentmaster_id = form.get("to_tentmaster_id")
        to_tentmaster_id = int(str(raw_tentmaster_id)) if raw_tentmaster_id else None
        JobService(session).reassign_phase_tentmaster(phase_id, to_tentmaster_id)
    except (JobError, ValueError) as error:
        return RedirectResponse(
            f"/planning?{suffix}&errors={quote(str(error))}", status_code=303
        )
    return RedirectResponse(f"/planning?{suffix}", status_code=303)


@router.get("/planning/flow", response_class=HTMLResponse, include_in_schema=False)
def flow_diagram(
    request: Request,
    session: SessionDependency,
    start: date | None = None,
    end: date | None = None,
    year: int | None = None,
) -> HTMLResponse:
    selected_start, selected_end = _range(start, end, year)
    try:
        flow = FlowService(session).build(selected_start, selected_end)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return templates.TemplateResponse(
        request=request,
        name="planning/flow_diagram.html",
        context={"flow": flow, "current_year": date.today().year},
    )


@router.get("/api/planning/board")
def board_data(
    session: SessionDependency,
    start: date | None = None,
    end: date | None = None,
    year: int | None = None,
) -> dict[str, object]:
    selected_start, selected_end = _range(start, end, year)
    try:
        return BoardService(session).build(selected_start, selected_end).jsonable()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
