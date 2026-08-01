from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.administration import EquipmentAsset, EquipmentType, Location, Tentmaster
from app.models.audit import AuditLog
from app.models.crew_movements import CrewMovement
from app.models.jobs import Job
from app.models.logistics import EquipmentMovement, Load


class BackupError(RuntimeError):
    pass


def backup_database(destination_directory: Path) -> Path:
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        raise BackupError("The local backup command currently supports SQLite databases")
    source = Path(url.database).resolve()
    if not source.exists():
        raise BackupError(f"Database not found: {source}")
    destination_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = destination_directory / f"kayam-{timestamp}.db"
    with sqlite3.connect(source) as source_db, sqlite3.connect(destination) as backup_db:
        source_db.backup(backup_db)
    return destination


def core_export(session: Session) -> dict[str, list[dict[str, Any]]]:
    models = (
        Location,
        EquipmentType,
        EquipmentAsset,
        Tentmaster,
        Job,
        EquipmentMovement,
        Load,
        CrewMovement,
    )
    result: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        rows = []
        for record in session.scalars(select(model).order_by(model.id)):
            values = {}
            for column in model.__table__.columns:
                value = getattr(record, column.name)
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                elif hasattr(value, "value"):
                    value = value.value
                values[column.name] = value
            rows.append(values)
        result[model.__tablename__] = rows
    return result


def write_core_export(session: Session, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(core_export(session), indent=2, default=str) + "\n")
    return destination


def recent_audit(session: Session, limit: int = 100) -> list[AuditLog]:
    return list(
        session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    )
