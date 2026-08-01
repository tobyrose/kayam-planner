from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.services.conflicts import ConflictCentreService
from app.services.logistics import LogisticsError, LogisticsService

router = APIRouter(tags=["conflicts"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


@router.get("/conflicts", response_class=HTMLResponse)
def conflicts_page(request: Request, session: SessionDependency) -> HTMLResponse:
    service = ConflictCentreService(session)
    conflicts = service.conflicts()
    return templates.TemplateResponse(
        request=request,
        name="conflicts/index.html",
        context={
            "conflicts": conflicts,
            "hard_count": sum(item.severity == "hard" for item in conflicts),
            "movement_suggestions": service.direct_movement_suggestions(),
            "spare_loads": service.spare_load_suggestions(),
        },
    )


@router.post("/conflicts/accept-movement", response_model=None)
async def accept_movement(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    try:
        LogisticsService(session).create_movement(
            {
                "movement_code": form.get("movement_code"),
                "origin_location_id": form.get("origin_location_id"),
                "destination_location_id": form.get("destination_location_id"),
                "depart_after": datetime.fromisoformat(str(form.get("depart_after"))),
                "arrive_by": datetime.fromisoformat(str(form.get("arrive_by"))),
                "status": "planned",
                "source": "manual",
            }
        )
    except (LogisticsError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return RedirectResponse("/conflicts", status_code=303)
