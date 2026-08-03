from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.models.administration import EquipmentType, Location, Tentmaster
from app.models.jobs import CommercialStatus, PhaseType, PlanningStatus, RecordSource
from app.services.administration import validation_messages
from app.services.crew_planning import CrewPlanningService
from app.services.jobs import JobError, JobNotFoundError, JobService
from app.services.roster import RosterIndex

router = APIRouter(tags=["jobs"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


def parse_datetime(value: Any) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(get_settings().default_timezone))
    return parsed


def job_payload(form: Any) -> dict[str, Any]:
    return {
        "job_code": form.get("job_code"),
        "name": form.get("name"),
        "customer_name": form.get("customer_name"),
        "location_id": form.get("location_id"),
        "commercial_status": form.get("commercial_status", CommercialStatus.ENQUIRY.value),
        "planning_status": form.get("planning_status", PlanningStatus.NOT_PLANNED.value),
        "confidence_percent": form.get("confidence_percent") or None,
        "contract_revenue": form.get("contract_revenue") or Decimal("0"),
        "currency": form.get("currency") or "GBP",
        "site_access_at": parse_datetime(form.get("site_access_at")),
        "site_clear_by": parse_datetime(form.get("site_clear_by")),
        "maintenance_cover_required": "maintenance_cover_required" in form,
        "catering_arrangement": form.get("catering_arrangement") or None,
        "accommodation_arrangement": form.get("accommodation_arrangement") or None,
        "ground_type": form.get("ground_type") or None,
        "build_scope": form.get("build_scope") or None,
        "strike_scope": form.get("strike_scope") or None,
        "operational_notes": form.get("operational_notes") or None,
        "commercial_notes": form.get("commercial_notes") or None,
        "deposit_received_at": parse_datetime(form.get("deposit_received_at")),
    }


def job_form_values(job: Any | None = None) -> dict[str, Any]:
    if job is None:
        return {
            "commercial_status": CommercialStatus.ENQUIRY.value,
            "planning_status": PlanningStatus.NOT_PLANNED.value,
            "currency": "GBP",
            "contract_revenue": "0",
        }
    names = (
        "job_code",
        "name",
        "customer_name",
        "location_id",
        "commercial_status",
        "planning_status",
        "confidence_percent",
        "contract_revenue",
        "currency",
        "site_access_at",
        "site_clear_by",
        "maintenance_cover_required",
        "catering_arrangement",
        "accommodation_arrangement",
        "ground_type",
        "build_scope",
        "strike_scope",
        "operational_notes",
        "commercial_notes",
        "deposit_received_at",
    )
    values = {}
    for name in names:
        value = getattr(job, name)
        if isinstance(value, datetime):
            values[name] = value.strftime("%Y-%m-%dT%H:%M")
        else:
            values[name] = getattr(value, "value", value)
    return values


def form_context(
    request: Request,
    session: Session,
    values: dict[str, Any],
    *,
    job_id: int | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "request": request,
        "values": values,
        "job_id": job_id,
        "errors": errors or [],
        "locations": session.scalars(
            select(Location).where(Location.active).order_by(Location.name)
        ).all(),
        "commercial_statuses": CommercialStatus,
        "planning_statuses": PlanningStatus,
    }


@router.get("/jobs", response_class=HTMLResponse)
def jobs_list(request: Request, session: SessionDependency) -> HTMLResponse:
    jobs = JobService(session).list_jobs()
    return templates.TemplateResponse(
        request=request, name="jobs/list.html", context={"jobs": jobs}
    )


@router.get("/jobs/new", response_class=HTMLResponse)
def new_job_form(request: Request, session: SessionDependency) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="jobs/form.html",
        context=form_context(request, session, job_form_values()),
    )


@router.post("/jobs/new", response_model=None)
async def create_job(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    payload = job_payload(form)
    try:
        job = JobService(session).create_job(payload)
    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="jobs/form.html",
            context=form_context(request, session, dict(form), errors=validation_messages(error)),
            status_code=422,
        )
    except JobError as error:
        return templates.TemplateResponse(
            request=request,
            name="jobs/form.html",
            context=form_context(request, session, dict(form), errors=[str(error)]),
            status_code=409,
        )
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


def _operational_context(session: Session, job: Any) -> dict[str, Any]:
    section_types = session.scalars(
        select(EquipmentType)
        .where(EquipmentType.category == "section", EquipmentType.active)
        .order_by(EquipmentType.tent_family_id, EquipmentType.code)
    ).all()
    ancillary_types = session.scalars(
        select(EquipmentType)
        .where(EquipmentType.category != "section", EquipmentType.active)
        .order_by(EquipmentType.code)
    ).all()
    tentmasters = session.scalars(
        select(Tentmaster).where(Tentmaster.active).order_by(Tentmaster.name)
    ).all()
    crew_planning = CrewPlanningService(session)
    if job.phases:
        roster_index = RosterIndex.build(
            session,
            min(phase.start_at for phase in job.phases),
            max(phase.end_at for phase in job.phases),
        )
        phase_headcounts = {
            phase.id: crew_planning.phase_headcount(phase, roster_index=roster_index)
            for phase in job.phases
        }
    else:
        phase_headcounts = {}
    return {
        "job": job,
        "section_types": section_types,
        "ancillary_types": ancillary_types,
        "tentmasters": tentmasters,
        "phase_types": PhaseType,
        "record_sources": RecordSource,
        "phase_headcounts": phase_headcounts,
    }


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int, session: SessionDependency) -> HTMLResponse:
    service = JobService(session)
    try:
        job = service.get_job(job_id)
    except JobNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return templates.TemplateResponse(
        request=request,
        name="jobs/detail.html",
        context=_operational_context(session, job),
    )


@router.get("/jobs/{job_id}/summary", response_class=HTMLResponse)
def job_summary(request: Request, job_id: int, session: SessionDependency) -> HTMLResponse:
    """A bare read-only fragment (no base.html) for the season board's job side panel."""
    service = JobService(session)
    try:
        job = service.get_job(job_id)
    except JobNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return templates.TemplateResponse(
        request=request,
        name="jobs/summary_fragment.html",
        context=_operational_context(session, job),
    )


@router.get("/jobs/{job_id}/edit", response_class=HTMLResponse)
def edit_job_form(request: Request, job_id: int, session: SessionDependency) -> HTMLResponse:
    service = JobService(session)
    try:
        job = service.get_job(job_id)
    except JobNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    context = form_context(request, session, job_form_values(job), job_id=job_id)
    context.update(_operational_context(session, job))
    return templates.TemplateResponse(request=request, name="jobs/form.html", context=context)


@router.post("/jobs/{job_id}/edit", response_model=None)
async def update_job(request: Request, job_id: int, session: SessionDependency) -> Response:
    form = await request.form()
    payload = job_payload(form)
    try:
        JobService(session).update_job(job_id, payload)
    except ValidationError as error:
        context = form_context(
            request,
            session,
            dict(form),
            job_id=job_id,
            errors=validation_messages(error),
        )
        context.update(_operational_context(session, JobService(session).get_job(job_id)))
        return templates.TemplateResponse(
            request=request, name="jobs/form.html", context=context, status_code=422
        )
    except JobError as error:
        context = form_context(request, session, dict(form), job_id=job_id, errors=[str(error)])
        context.update(_operational_context(session, JobService(session).get_job(job_id)))
        return templates.TemplateResponse(
            request=request, name="jobs/form.html", context=context, status_code=409
        )
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/tent-requirements", response_model=None)
async def add_tent_requirement(
    request: Request, job_id: int, session: SessionDependency
) -> Response:
    form = await request.form()
    payload = {
        "sequence": form.get("sequence"),
        "quantity": form.get("quantity"),
        "custom_name": form.get("custom_name") or None,
        "contracted_up_at": parse_datetime(form.get("contracted_up_at")),
        "contracted_down_at": parse_datetime(form.get("contracted_down_at")),
        "notes": form.get("notes") or None,
    }
    try:
        JobService(session).add_tent_requirement(job_id, payload)
    except (ValidationError, JobError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse(f"/jobs/{job_id}#tent-requirements", status_code=303)


@router.post("/jobs/{job_id}/tent-requirements/{requirement_id}/delete", response_model=None)
def delete_tent_requirement(
    job_id: int, requirement_id: int, session: SessionDependency
) -> Response:
    try:
        JobService(session).delete_tent_requirement(job_id, requirement_id)
    except JobNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return RedirectResponse(f"/jobs/{job_id}#tent-requirements", status_code=303)


@router.post("/jobs/{job_id}/regenerate", response_model=None)
def regenerate_job(job_id: int, session: SessionDependency) -> Response:
    service = JobService(session)
    job = service.get_job(job_id)
    try:
        service.regenerate_requirements(job)
    except JobError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    session.commit()
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/phases/{phase_id}", response_model=None)
async def update_phase(
    request: Request, job_id: int, phase_id: int, session: SessionDependency
) -> Response:
    form = await request.form()
    payload = {
        "phase_type": form.get("phase_type"),
        "job_tent_requirement_id": form.get("job_tent_requirement_id") or None,
        "tentmaster_id": form.get("tentmaster_id") or None,
        "start_at": parse_datetime(form.get("start_at")),
        "end_at": parse_datetime(form.get("end_at")),
        "required_headcount": form.get("required_headcount") or 0,
        "notes": form.get("notes") or None,
        "locked": "locked" in form,
        "source": RecordSource.MANUAL.value,
    }
    try:
        JobService(session).update_phase(job_id, phase_id, payload)
    except (ValidationError, JobError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse(f"/jobs/{job_id}#phases", status_code=303)


@router.post("/jobs/{job_id}/phases/new", response_model=None)
async def add_phase(request: Request, job_id: int, session: SessionDependency) -> Response:
    form = await request.form()
    payload = {
        "phase_type": form.get("phase_type"),
        "job_tent_requirement_id": form.get("job_tent_requirement_id") or None,
        "tentmaster_id": form.get("tentmaster_id") or None,
        "start_at": parse_datetime(form.get("start_at")),
        "end_at": parse_datetime(form.get("end_at")),
        "required_headcount": form.get("required_headcount") or 0,
        "notes": form.get("notes") or None,
        "locked": False,
    }
    try:
        JobService(session).add_phase(job_id, payload)
    except (ValidationError, JobError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse(f"/jobs/{job_id}#phases", status_code=303)


@router.post("/jobs/{job_id}/phases/{phase_id}/delete", response_model=None)
def delete_phase(job_id: int, phase_id: int, session: SessionDependency) -> Response:
    try:
        JobService(session).delete_phase(job_id, phase_id)
    except JobError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse(f"/jobs/{job_id}#phases", status_code=303)


@router.post("/jobs/{job_id}/local-crew", response_model=None)
async def add_local_crew(request: Request, job_id: int, session: SessionDependency) -> Response:
    form = await request.form()
    payload = {
        "headcount": form.get("headcount"),
        "start_at": parse_datetime(form.get("start_at")),
        "end_at": parse_datetime(form.get("end_at")),
        "notes": form.get("notes") or None,
    }
    try:
        JobService(session).add_local_crew_booking(job_id, payload)
    except (ValidationError, JobError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse(f"/jobs/{job_id}#phases", status_code=303)


@router.post("/jobs/{job_id}/local-crew/{booking_id}/delete", response_model=None)
def delete_local_crew(job_id: int, booking_id: int, session: SessionDependency) -> Response:
    try:
        JobService(session).delete_local_crew_booking(job_id, booking_id)
    except JobError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse(f"/jobs/{job_id}#phases", status_code=303)


@router.post("/jobs/{job_id}/ancillary-equipment", response_model=None)
async def add_ancillary_equipment(
    request: Request, job_id: int, session: SessionDependency
) -> Response:
    form = await request.form()
    try:
        equipment_type_id = int(str(form.get("equipment_type_id")))
        quantity = int(str(form.get("quantity") or 1))
        JobService(session).add_ancillary_equipment(job_id, equipment_type_id, quantity)
    except (ValueError, JobError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse(f"/jobs/{job_id}#loading-list", status_code=303)
