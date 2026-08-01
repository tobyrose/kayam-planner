from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.main_paths import TEMPLATE_DIRECTORY
from app.models.costing import CostCategory, LoadCostAllocation, SupplierInvoice
from app.models.jobs import Job
from app.models.logistics import Load
from app.services.costing import CostingError, CostingService

router = APIRouter(tags=["costing"], include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
SessionDependency = Annotated[Session, Depends(get_db_session)]


@router.get("/costs", response_class=HTMLResponse)
def costs_page(request: Request, session: SessionDependency) -> HTMLResponse:
    jobs = session.scalars(select(Job).order_by(Job.site_access_at)).all()
    loads = session.scalars(select(Load).order_by(Load.id)).all()
    service = CostingService(session)
    return templates.TemplateResponse(
        request=request,
        name="costing/index.html",
        context={
            "jobs": jobs,
            "summaries": {job.id: service.job_summary(job) for job in jobs},
            "invoices": session.scalars(
                select(SupplierInvoice).order_by(SupplierInvoice.invoice_date.desc())
            ).all(),
            "loads": loads,
            "load_actuals": {load.id: service.load_actual_cost(load.id) for load in loads},
            "load_variances": {load.id: service.load_variance(load) for load in loads},
            "categories": CostCategory,
        },
    )


@router.post("/costs/invoices", response_model=None)
async def create_invoice(request: Request, session: SessionDependency) -> Response:
    form = await request.form()
    invoice = SupplierInvoice(
        supplier_reference=str(form.get("supplier_reference")),
        supplier_name=str(form.get("supplier_name")),
        invoice_date=date.fromisoformat(str(form.get("invoice_date"))),
        total_amount=Decimal(str(form.get("total_amount"))),
        currency=str(form.get("currency") or "GBP"),
    )
    session.add(invoice)
    session.commit()
    return RedirectResponse("/costs", status_code=303)


@router.post("/costs/invoices/{invoice_id}/allocate", response_model=None)
async def allocate_invoice(
    request: Request, invoice_id: int, session: SessionDependency
) -> Response:
    invoice = session.get(SupplierInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    form = await request.form()
    allocation = LoadCostAllocation(
        supplier_invoice_id=invoice.id,
        load_id=int(str(form.get("load_id"))),
        job_id=int(str(form["job_id"])) if form.get("job_id") else None,
        category=CostCategory(str(form.get("category"))),
        allocated_amount=Decimal(str(form.get("allocated_amount"))),
    )
    try:
        CostingService(session).allocate_invoice(invoice, [allocation])
    except CostingError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return RedirectResponse("/costs", status_code=303)
