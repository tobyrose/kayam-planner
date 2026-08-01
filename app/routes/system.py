from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.services.system import backup_database, core_export, recent_audit

router = APIRouter(prefix="/system", tags=["system"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


@router.get("", response_class=HTMLResponse)
def system_page(
    request: Request, session: SessionDependency, backup: str | None = None
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="system/index.html",
        context={"audit": recent_audit(session), "backup": backup},
    )


@router.post("/backup", response_model=None)
def create_backup() -> Response:
    destination = backup_database(Path("backups"))
    return RedirectResponse(f"/system?backup={destination.name}", status_code=303)


@router.get("/export.json")
def export_json(session: SessionDependency) -> Response:
    return Response(
        json.dumps(core_export(session), indent=2, default=str) + "\n",
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="kayam-export.json"'},
    )
