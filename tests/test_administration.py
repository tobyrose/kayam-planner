from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import (
    BuildStage,
    CrewMember,
    EquipmentAsset,
    EquipmentType,
    Location,
    LocationType,
    TentConfiguration,
    TentConfigurationRequirement,
    TentFamily,
    Tentmaster,
    TrackingMode,
)
from app.schemas.administration import LocationData, LorryTypeData
from app.services.administration import AdministrationService, MembershipOverlapError
from app.services.administration_catalog import ENTITY_BY_SLUG


def add_core_references(session: Session) -> tuple[Location, TentFamily, EquipmentType]:
    location = Location(name="Test Yard", location_type=LocationType.YARD)
    family = TentFamily(name="Test family")
    session.add_all([location, family])
    session.flush()
    equipment_type = EquipmentType(
        code="END",
        name="End",
        category="section",
        tent_family_id=family.id,
        tracking_mode=TrackingMode.INDIVIDUAL,
        default_build_stage=BuildStage.MAIN_SECTIONS,
    )
    session.add(equipment_type)
    session.commit()
    return location, family, equipment_type


def test_asset_code_is_unique(session: Session) -> None:
    location, _, equipment_type = add_core_references(session)
    session.add(
        EquipmentAsset(
            asset_code="K1",
            equipment_type_id=equipment_type.id,
            initial_location_id=location.id,
        )
    )
    session.commit()

    session.add(
        EquipmentAsset(
            asset_code="K1",
            equipment_type_id=equipment_type.id,
            initial_location_id=location.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_tentmaster_membership_overlap_is_rejected(session: Session) -> None:
    location = Location(name="Membership Yard", location_type=LocationType.YARD)
    crew_member = CrewMember(name="Test Person", role="Crew", employment_type="Test")
    first_team = Tentmaster(name="First team")
    second_team = Tentmaster(name="Second team")
    session.add_all([location, crew_member, first_team, second_team])
    session.commit()
    service = AdministrationService(session)
    definition = ENTITY_BY_SLUG["tentmaster-memberships"]

    service.create(
        definition,
        {
            "tentmaster_id": first_team.id,
            "crew_member_id": crew_member.id,
            "start_at": date(2026, 1, 1),
            "end_at": date(2026, 6, 30),
            "is_default": True,
            "notes": None,
        },
    )

    with pytest.raises(MembershipOverlapError):
        service.create(
            definition,
            {
                "tentmaster_id": second_team.id,
                "crew_member_id": crew_member.id,
                "start_at": date(2026, 6, 1),
                "end_at": None,
                "is_default": True,
                "notes": None,
            },
        )


def test_tent_configuration_requirements_are_configurable(session: Session) -> None:
    _, family, end_type = add_core_references(session)
    middle_type = EquipmentType(
        code="MIDDLE",
        name="Middle",
        category="section",
        tent_family_id=family.id,
        default_build_stage=BuildStage.MAIN_SECTIONS,
    )
    session.add(middle_type)
    session.flush()
    configuration = TentConfiguration(
        tent_family_id=family.id,
        name="Test 10-pole",
        pole_count=10,
        minimum_crew=4,
        preferred_crew=6,
    )
    session.add(configuration)
    session.flush()
    session.add_all(
        [
            TentConfigurationRequirement(
                tent_configuration_id=configuration.id,
                equipment_type_id=end_type.id,
                quantity=2,
                required_stage=BuildStage.MAIN_SECTIONS,
            ),
            TentConfigurationRequirement(
                tent_configuration_id=configuration.id,
                equipment_type_id=middle_type.id,
                quantity=4,
                required_stage=BuildStage.MAIN_SECTIONS,
            ),
        ]
    )
    session.commit()

    quantities = {item.equipment_type.code: item.quantity for item in configuration.requirements}
    assert quantities == {"END": 2, "MIDDLE": 4}


def test_lorry_capacity_fields_reject_negative_values() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        LorryTypeData(
            name="Invalid",
            section_capacity_units=Decimal("-1"),
            pole_capacity_units=Decimal("0"),
            ancillary_capacity_units=Decimal("0"),
            payload_kg=Decimal("0"),
            passenger_capacity=0,
            default_cost_per_km=Decimal("0"),
            minimum_load_cost=Decimal("0"),
        )


def test_location_timezone_must_be_valid() -> None:
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        LocationData(name="Invalid timezone", timezone="Europe/NotAPlace")


def test_development_seed_is_idempotent_and_clearly_demonstrative(session: Session) -> None:
    first_created = seed_development_data(session)
    second_created = seed_development_data(session)

    assert first_created > 0
    assert second_created == 0
    oxford = session.query(Location).filter_by(name="Oxford Yard").one()
    assert oxford.location_type == LocationType.YARD
    assert "DEMONSTRATION DATA" in (oxford.access_notes or "")
