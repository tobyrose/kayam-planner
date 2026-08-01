from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AwareDateTime, Base
from app.models.administration import Haulier
from app.models.jobs import Job
from app.models.logistics import Load


class CostCategory(StrEnum):
    HAULAGE = "haulage"
    FUEL = "fuel"
    FERRY = "ferry"
    FLIGHT = "flight"
    ACCOMMODATION = "accommodation"
    LABOUR = "labour"
    ALLOWANCE = "allowance"
    OTHER = "other"


class SupplierInvoice(Base):
    __tablename__ = "supplier_invoices"
    __table_args__ = (
        UniqueConstraint("supplier_reference"),
        CheckConstraint("total_amount >= 0", name="total_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_reference: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    haulier_id: Mapped[int | None] = mapped_column(ForeignKey("hauliers.id"))
    supplier_name: Mapped[str] = mapped_column(String(200))
    invoice_date: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    received_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    notes: Mapped[str | None] = mapped_column(Text)

    haulier: Mapped[Haulier | None] = relationship()
    allocations: Mapped[list[LoadCostAllocation]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class LoadCostAllocation(Base):
    __tablename__ = "load_cost_allocations"
    __table_args__ = (
        UniqueConstraint("supplier_invoice_id", "load_id", "job_id", "category"),
        CheckConstraint("allocated_amount >= 0", name="amount_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_invoices.id", ondelete="CASCADE"), index=True
    )
    load_id: Mapped[int] = mapped_column(ForeignKey("loads.id"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), index=True)
    category: Mapped[CostCategory] = mapped_column(String(30), default=CostCategory.HAULAGE)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    invoice: Mapped[SupplierInvoice] = relationship(back_populates="allocations")
    load: Mapped[Load] = relationship()
    job: Mapped[Job | None] = relationship()
