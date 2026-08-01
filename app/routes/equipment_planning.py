from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.models.administration import EquipmentAsset
from app.models.equipment_planning import AllocationStrength
from app.models.jobs import JobEquipmentRequirement, RecordSource
from app.routes.jobs import parse_datetime
from app.services.equipment_planning import EquipmentPlanningError, EquipmentPlanningService

router = APIRouter(tags=["equipment planning"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


@router.get("/equipment", response_class=HTMLResponse)
def equipment_list(request: Request, session: SessionDependency) -> HTMLResponse:
    assets = session.scalars(select(EquipmentAsset).order_by(EquipmentAsset.asset_code)).all()
    return templates.TemplateResponse(
        request=request, name="equipment/list.html", context={"assets": assets}
    )


@router.get("/equipment/{asset_id}", response_class=HTMLResponse)
def equipment_detail(request: Request, asset_id: int, session: SessionDependency) -> HTMLResponse:
    asset = session.get(EquipmentAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    timeline = EquipmentPlanningService(session).timeline(asset.id)
    return templates.TemplateResponse(
        request=request,
        name="equipment/detail.html",
        context={"asset": asset, "timeline": timeline},
    )


@router.get("/jobs/{job_id}/equipment/{requirement_id}/assign", response_class=HTMLResponse)
def assignment_form(
    request: Request,
    job_id: int,
    requirement_id: int,
    session: SessionDependency,
) -> HTMLResponse:
    requirement = session.get(JobEquipmentRequirement, requirement_id)
    if requirement is None or requirement.job_id != job_id:
        raise HTTPException(status_code=404, detail="Equipment requirement not found")
    candidates = EquipmentPlanningService(session).candidates(requirement)
    return templates.TemplateResponse(
        request=request,
        name="equipment/assignment_form.html",
        context={
            "requirement": requirement,
            "candidates": candidates,
            "strengths": AllocationStrength,
            "errors": [],
        },
    )


@router.post("/jobs/{job_id}/equipment/{requirement_id}/assign", response_model=None)
async def create_assignment(
    request: Request,
    job_id: int,
    requirement_id: int,
    session: SessionDependency,
) -> Response:
    requirement = session.get(JobEquipmentRequirement, requirement_id)
    if requirement is None or requirement.job_id != job_id:
        raise HTTPException(status_code=404, detail="Equipment requirement not found")
    form = await request.form()
    payload = {
        "job_equipment_requirement_id": requirement.id,
        "equipment_asset_id": form.get("equipment_asset_id"),
        "start_at": parse_datetime(form.get("start_at")),
        "end_at": parse_datetime(form.get("end_at")),
        "allocation_strength": form.get("allocation_strength") or "soft",
        "assignment_source": RecordSource.MANUAL.value,
        "locked": "locked" in form,
        "status": "active",
        "notes": form.get("notes") or None,
    }
    service = EquipmentPlanningService(session)
    try:
        service.assign(payload)
    except (ValidationError, EquipmentPlanningError) as error:
        return templates.TemplateResponse(
            request=request,
            name="equipment/assignment_form.html",
            context={
                "requirement": requirement,
                "candidates": service.candidates(requirement),
                "strengths": AllocationStrength,
                "errors": [str(error)],
            },
            status_code=422,
        )
    return RedirectResponse(f"/jobs/{job_id}#equipment-assignments", status_code=303)


@router.post("/jobs/{job_id}/confirm", response_model=None)
async def confirm_job(request: Request, job_id: int, session: SessionDependency) -> Response:
    form = await request.form()
    assignment_ids = [int(str(value)) for value in form.getlist("assignment_ids")]
    try:
        EquipmentPlanningService(session).confirm_job(job_id, assignment_ids, lock=True)
    except EquipmentPlanningError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)
