from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.models.administration import CrewMember, EquipmentType
from app.services.administration import (
    AdministrationError,
    AdministrationService,
    RecordNotFoundError,
    validation_messages,
)
from app.services.administration_catalog import (
    ENTITY_BY_SLUG,
    EntityDefinition,
    grouped_entities,
)

router = APIRouter(prefix="/admin", tags=["administration"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


def get_definition(entity_slug: str) -> EntityDefinition:
    definition = ENTITY_BY_SLUG.get(entity_slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Administration section not found")
    return definition


def _redirect_target(candidate: str | None, default: str) -> str:
    """Only ever redirect back into /admin/ — never trust an open redirect target."""
    if candidate and candidate.startswith("/admin/"):
        return candidate
    return default


def form_values(definition: EntityDefinition, form: FormData) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in definition.fields:
        if field.kind == "checkbox":
            values[field.name] = field.name in form
            continue
        value = form.get(field.name)
        values[field.name] = None if value is None or str(value).strip() == "" else str(value)
    return values


def initial_values(
    definition: EntityDefinition, request: Request, service: AdministrationService
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in definition.fields:
        values[field.name] = (
            field.default
            if field.default is not None
            else service.default_option_for(field)
        )
    for field in definition.fields:
        query_value = request.query_params.get(field.name)
        if query_value is not None:
            values[field.name] = query_value
    return values


def record_values(definition: EntityDefinition, record: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in definition.fields:
        value = getattr(record, field.name)
        if value is None:
            values[field.name] = None
        elif hasattr(value, "isoformat"):
            values[field.name] = value.isoformat()
        else:
            values[field.name] = getattr(value, "value", value)
    return values


def form_context(
    request: Request,
    definition: EntityDefinition,
    service: AdministrationService,
    values: dict[str, Any],
    *,
    errors: list[str] | None = None,
    record_id: int | None = None,
) -> dict[str, Any]:
    options = {field.name: service.options_for(field) for field in definition.fields}
    return {
        "request": request,
        "entity": definition,
        "values": values,
        "options": options,
        "errors": errors or [],
        "record_id": record_id,
    }


@router.get("", response_class=HTMLResponse)
def administration_home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="admin/index.html",
        context={"groups": grouped_entities()},
    )


@router.get("/{entity_slug}", response_class=HTMLResponse)
def list_records(
    request: Request,
    entity_slug: str,
    session: SessionDependency,
) -> HTMLResponse:
    definition = get_definition(entity_slug)
    service = AdministrationService(session)
    rows = [
        {
            "id": record.id,
            "values": [
                service.display_value(record, definition.field(field_name))
                for field_name in definition.list_fields
            ],
        }
        for record in service.list_records(definition)
    ]
    return templates.TemplateResponse(
        request=request,
        name="admin/list.html",
        context={"entity": definition, "rows": rows},
    )


@router.get("/{entity_slug}/new", response_class=HTMLResponse)
def new_record_form(
    request: Request,
    entity_slug: str,
    session: SessionDependency,
) -> HTMLResponse:
    definition = get_definition(entity_slug)
    service = AdministrationService(session)
    return templates.TemplateResponse(
        request=request,
        name="admin/form.html",
        context=form_context(
            request, definition, service, initial_values(definition, request, service)
        ),
    )


@router.post("/{entity_slug}/new", response_model=None)
async def create_record(
    request: Request,
    entity_slug: str,
    session: SessionDependency,
) -> Response:
    definition = get_definition(entity_slug)
    service = AdministrationService(session)
    form = await request.form()
    redirect_to = _redirect_target(
        str(form.get("redirect_to")) if form.get("redirect_to") else None,
        "",
    )
    payload = form_values(definition, form)
    try:
        record = service.create(definition, payload)
    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/form.html",
            context=form_context(
                request,
                definition,
                service,
                payload,
                errors=validation_messages(error),
            ),
            status_code=422,
        )
    except AdministrationError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/form.html",
            context=form_context(request, definition, service, payload, errors=[str(error)]),
            status_code=409,
        )
    return RedirectResponse(redirect_to or f"/admin/{entity_slug}/{record.id}", status_code=303)


@router.get("/{entity_slug}/{record_id}", response_class=HTMLResponse)
def record_detail(
    request: Request,
    entity_slug: str,
    record_id: int,
    session: SessionDependency,
) -> HTMLResponse:
    definition = get_definition(entity_slug)
    service = AdministrationService(session)
    try:
        record = service.get_record(definition, record_id)
    except RecordNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    details = [(field.label, service.display_value(record, field)) for field in definition.fields]
    components = []
    if isinstance(record, EquipmentType):
        components = [
            {
                "id": link.id,
                "equipment_type": link.child_equipment_type.code,
                "quantity": link.quantity_per_parent,
                "stage": "",
            }
            for link in record.outgoing_links
        ]
    return templates.TemplateResponse(
        request=request,
        name="admin/detail.html",
        context={
            "entity": definition,
            "record": record,
            "details": details,
            "components": components,
        },
    )


@router.get("/{entity_slug}/{record_id}/edit", response_class=HTMLResponse)
def edit_record_form(
    request: Request,
    entity_slug: str,
    record_id: int,
    session: SessionDependency,
) -> HTMLResponse:
    definition = get_definition(entity_slug)
    service = AdministrationService(session)
    try:
        record = service.get_record(definition, record_id)
    except RecordNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    context = form_context(
        request,
        definition,
        service,
        record_values(definition, record),
        record_id=record_id,
    )
    if isinstance(record, CrewMember):
        context["availability"] = sorted(record.availability, key=lambda row: row.start_at)
        context["availability_windows"] = sorted(
            record.availability_windows, key=lambda row: row.start_at
        )
        context["availability_statuses"] = ENTITY_BY_SLUG["crew-availability"].field(
            "status"
        ).choices
    return templates.TemplateResponse(request=request, name="admin/form.html", context=context)


@router.post("/{entity_slug}/{record_id}/edit", response_model=None)
async def update_record(
    request: Request,
    entity_slug: str,
    record_id: int,
    session: SessionDependency,
) -> Response:
    definition = get_definition(entity_slug)
    service = AdministrationService(session)
    form = await request.form()
    redirect_to = _redirect_target(
        str(form.get("redirect_to")) if form.get("redirect_to") else None,
        "",
    )
    payload = form_values(definition, form)
    try:
        service.update(definition, record_id, payload)
    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/form.html",
            context=form_context(
                request,
                definition,
                service,
                payload,
                errors=validation_messages(error),
                record_id=record_id,
            ),
            status_code=422,
        )
    except AdministrationError as error:
        status_code = 404 if isinstance(error, RecordNotFoundError) else 409
        return templates.TemplateResponse(
            request=request,
            name="admin/form.html",
            context=form_context(
                request,
                definition,
                service,
                payload,
                errors=[str(error)],
                record_id=record_id,
            ),
            status_code=status_code,
        )
    return RedirectResponse(redirect_to or f"/admin/{entity_slug}/{record_id}", status_code=303)


@router.post("/{entity_slug}/{record_id}/delete", response_model=None)
def delete_record(
    entity_slug: str,
    record_id: int,
    session: SessionDependency,
    redirect_to: str | None = None,
) -> Response:
    definition = get_definition(entity_slug)
    service = AdministrationService(session)
    try:
        service.delete(definition, record_id)
    except RecordNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AdministrationError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return RedirectResponse(
        _redirect_target(redirect_to, f"/admin/{entity_slug}"), status_code=303
    )
