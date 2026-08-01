from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, String, event, inspect
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database import AwareDateTime, Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[int | None] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(30), index=True)
    actor: Mapped[str] = mapped_column(String(150), default="local planner")
    changes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=lambda: datetime.now(UTC), index=True
    )


AUDITED_TABLES = {
    "jobs",
    "crew_assignments",
    "equipment_assignments",
    "equipment_movements",
    "loads",
    "load_items",
    "crew_movements",
    "crew_journey_legs",
    "crew_movement_passengers",
    "supplier_invoices",
    "load_cost_allocations",
}


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return str(value)


@event.listens_for(Session, "before_flush")
def collect_audit_changes(session: Session, _flush_context: object, _instances: object) -> None:
    if session.info.get("audit_in_progress"):
        return
    pending: list[tuple[Any, str, dict[str, Any]]] = []
    for obj in session.new:
        table = getattr(obj, "__tablename__", None)
        if table in AUDITED_TABLES:
            values = {
                attr.key: _safe(getattr(obj, attr.key))
                for attr in inspect(obj).mapper.column_attrs
                if attr.key != "id"
            }
            pending.append((obj, "create", values))
    for obj in session.dirty:
        table = getattr(obj, "__tablename__", None)
        if table not in AUDITED_TABLES or not session.is_modified(obj, include_collections=False):
            continue
        changes = {}
        state = inspect(obj)
        for attr in state.mapper.column_attrs:
            history = state.attrs[attr.key].history
            if history.has_changes():
                changes[attr.key] = {
                    "from": _safe(history.deleted[0]) if history.deleted else None,
                    "to": _safe(history.added[0]) if history.added else None,
                }
        pending.append((obj, "update", changes))
    for obj in session.deleted:
        if getattr(obj, "__tablename__", None) in AUDITED_TABLES:
            pending.append((obj, "delete", {}))
    if pending:
        session.info.setdefault("audit_pending", []).extend(pending)


@event.listens_for(Session, "after_flush_postexec")
def write_audit_changes(session: Session, _flush_context: object) -> None:
    pending = session.info.pop("audit_pending", [])
    if not pending:
        return
    session.info["audit_in_progress"] = True
    try:
        for obj, action, changes in pending:
            session.add(
                AuditLog(
                    entity_type=obj.__tablename__,
                    entity_id=getattr(obj, "id", None),
                    action=action,
                    changes=changes,
                )
            )
    finally:
        session.info["audit_in_progress"] = False
