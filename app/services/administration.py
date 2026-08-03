from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.administration import TentmasterMembership
from app.repositories.administration import AdministrationRepository
from app.services.administration_catalog import EntityDefinition, FormField


class AdministrationError(Exception):
    """Base exception for safe administration feedback."""


class RecordNotFoundError(AdministrationError):
    pass


class RecordConflictError(AdministrationError):
    pass


class MembershipOverlapError(AdministrationError):
    pass


class AdministrationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AdministrationRepository(session)

    def list_records(self, definition: EntityDefinition) -> list[Any]:
        return self.repository.list(definition.model)

    def get_record(self, definition: EntityDefinition, record_id: int) -> Any:
        record = self.repository.get(definition.model, record_id)
        if record is None:
            raise RecordNotFoundError(f"{definition.singular} not found")
        return record

    def validate(self, definition: EntityDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        validated = definition.schema.model_validate(payload)
        return validated.model_dump()

    def create(self, definition: EntityDefinition, payload: dict[str, Any]) -> Any:
        values = self.validate(definition, payload)
        self._validate_membership_overlap(definition, values)
        try:
            record = self.repository.create(definition.model, values)
            self.session.commit()
            self.session.refresh(record)
            return record
        except IntegrityError as error:
            self.session.rollback()
            raise RecordConflictError(self._integrity_message(definition)) from error

    def update(self, definition: EntityDefinition, record_id: int, payload: dict[str, Any]) -> Any:
        record = self.get_record(definition, record_id)
        values = self.validate(definition, payload)
        self._validate_membership_overlap(definition, values, exclude_id=record_id)
        try:
            self.repository.update(record, values)
            self.session.commit()
            self.session.refresh(record)
            return record
        except IntegrityError as error:
            self.session.rollback()
            raise RecordConflictError(self._integrity_message(definition)) from error

    def delete(self, definition: EntityDefinition, record_id: int) -> None:
        record = self.get_record(definition, record_id)
        try:
            self.repository.delete(record)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise RecordConflictError(
                f"{definition.singular} is referenced by other records and cannot be deleted."
            ) from error

    def options_for(self, field: FormField) -> list[tuple[int, str]]:
        if field.option_model is None:
            return []
        records = self.repository.list(field.option_model)
        return [(record.id, str(getattr(record, field.option_label))) for record in records]

    def default_option_for(self, field: FormField) -> int | None:
        """The id of `field.option_model`'s `is_default=True` row, if that model has one."""
        if field.option_model is None or not hasattr(field.option_model, "is_default"):
            return None
        for record in self.repository.list(field.option_model):
            if getattr(record, "is_default", False):
                return int(record.id)
        return None

    def display_value(self, record: Any, field: FormField) -> str:
        value = getattr(record, field.name)
        if value is None:
            return "—"
        if field.option_model is not None:
            related = self.repository.get(field.option_model, int(value))
            return "—" if related is None else str(getattr(related, field.option_label))
        if isinstance(value, bool):
            return "Yes" if value else "No"
        return str(getattr(value, "value", value)).replace("_", " ")

    def _validate_membership_overlap(
        self,
        definition: EntityDefinition,
        values: dict[str, Any],
        *,
        exclude_id: int | None = None,
    ) -> None:
        if definition.model is not TentmasterMembership:
            return
        conditions = [
            TentmasterMembership.crew_member_id == values["crew_member_id"],
            or_(
                TentmasterMembership.end_at.is_(None),
                TentmasterMembership.end_at > values["start_at"],
            ),
        ]
        if values["end_at"] is not None:
            conditions.append(TentmasterMembership.start_at < values["end_at"])
        if exclude_id is not None:
            conditions.append(TentmasterMembership.id != exclude_id)
        overlap = self.session.scalar(select(TentmasterMembership.id).where(*conditions).limit(1))
        if overlap is not None:
            raise MembershipOverlapError(
                "This crew member already has a Tentmaster membership in that date range."
            )

    @staticmethod
    def _integrity_message(definition: EntityDefinition) -> str:
        if definition.model is TentmasterMembership:
            return "That membership conflicts with existing administration data."
        return f"{definition.singular} conflicts with an existing record or invalid reference."


def validation_messages(error: ValidationError) -> list[str]:
    messages = []
    for item in error.errors():
        field_name = str(item["loc"][-1]).replace("_", " ").title()
        messages.append(f"{field_name}: {item['msg']}")
    return messages
