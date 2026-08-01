from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.services.board import BoardService

router = APIRouter(tags=["seasonal planning"])
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _range(start: date | None, end: date | None) -> tuple[date, date]:
    today = date.today()
    default_start = date(today.year, 4, 1)
    return start or default_start, end or (default_start + timedelta(days=183))


@router.get("/planning", response_class=HTMLResponse, include_in_schema=False)
def combined_board(
    request: Request,
    session: SessionDependency,
    start: date | None = None,
    end: date | None = None,
) -> HTMLResponse:
    selected_start, selected_end = _range(start, end)
    try:
        board = BoardService(session).build(selected_start, selected_end)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return templates.TemplateResponse(
        request=request, name="planning/combined_board.html", context={"board": board}
    )


@router.get("/api/planning/board")
def board_data(
    session: SessionDependency,
    start: date | None = None,
    end: date | None = None,
) -> dict[str, object]:
    selected_start, selected_end = _range(start, end)
    try:
        return BoardService(session).build(selected_start, selected_end).jsonable()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
