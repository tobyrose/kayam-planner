from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base


class AdministrationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, model: type[Base]) -> list[Any]:
        model_id = cast(Any, model).id
        return list(self.session.scalars(select(model).order_by(model_id)).all())

    def get(self, model: type[Base], record_id: int) -> Any | None:
        return self.session.get(model, record_id)

    def create(self, model: type[Base], values: dict[str, Any]) -> Any:
        record = model(**values)
        self.session.add(record)
        self.session.flush()
        return record

    def update(self, record: Any, values: dict[str, Any]) -> Any:
        for name, value in values.items():
            setattr(record, name, value)
        self.session.flush()
        return record

    def delete(self, record: Any) -> None:
        self.session.delete(record)
        self.session.flush()
