from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from app.database import Base
from app.models.administration import (
    BuildStage,
    CrewAvailability,
    CrewAvailabilityStatus,
    CrewAvailabilityWindow,
    CrewEmploymentType,
    CrewMember,
    CrewRole,
    EquipmentAsset,
    EquipmentLink,
    EquipmentType,
    Haulier,
    Location,
    LocationType,
    Lorry,
    LorryType,
    OwnershipType,
    TentFamily,
    Tentmaster,
    TentmasterMembership,
    TrackingMode,
    Van,
)
from app.schemas.administration import (
    CrewAvailabilityData,
    CrewAvailabilityWindowData,
    CrewEmploymentTypeData,
    CrewMemberData,
    CrewRoleData,
    EquipmentAssetData,
    EquipmentLinkData,
    EquipmentTypeData,
    HaulierData,
    LocationData,
    LorryData,
    LorryTypeData,
    TentFamilyData,
    TentmasterData,
    TentmasterMembershipData,
    VanData,
)


def enum_choices(enum_type: type[StrEnum]) -> tuple[tuple[str, str], ...]:
    return tuple((item.value, item.value.replace("_", " ").title()) for item in enum_type)


@dataclass(frozen=True)
class FormField:
    name: str
    label: str
    kind: str = "text"
    required: bool = False
    default: Any = None
    choices: tuple[tuple[str, str], ...] = ()
    option_model: type[Base] | None = None
    option_label: str = "name"
    step: str | None = None
    help_text: str | None = None


@dataclass(frozen=True)
class EntityDefinition:
    slug: str
    singular: str
    plural: str
    group: str
    model: type[Base]
    schema: type[BaseModel]
    fields: tuple[FormField, ...]
    list_fields: tuple[str, ...]
    hidden: bool = False
    """Excluded from the admin home index and top-level nav when the entity is only ever
    edited nested inside another record's page (e.g. crew availability, edited from the crew
    member's own edit page) rather than browsed as its own section."""

    def field(self, name: str) -> FormField:
        return next(field for field in self.fields if field.name == name)


ACTIVE = FormField("active", "Active", "checkbox", default=True)
NOTES = FormField("notes", "Notes", "textarea")
MONEY_STEP = "0.01"
CAPACITY_STEP = "0.01"

ENTITY_DEFINITIONS = (
    EntityDefinition(
        "locations",
        "Location",
        "Locations",
        "Locations",
        Location,
        LocationData,
        (
            FormField("name", "Name", required=True),
            FormField(
                "location_type",
                "Location type",
                "select",
                required=True,
                default=LocationType.SITE.value,
                choices=enum_choices(LocationType),
            ),
            FormField("address_line_1", "Address line 1"),
            FormField("address_line_2", "Address line 2"),
            FormField("city", "City"),
            FormField("region", "Region"),
            FormField("postcode", "Postcode"),
            FormField("country_code", "Country code", default="GB"),
            FormField("latitude", "Latitude", "number", step="0.000001"),
            FormField("longitude", "Longitude", "number", step="0.000001"),
            FormField(
                "timezone",
                "Timezone",
                required=True,
                default="Europe/London",
                help_text="Use an IANA timezone such as Europe/London.",
            ),
            FormField(
                "default_unload_duration_minutes",
                "Default unload duration (minutes)",
                "number",
                required=True,
                default=60,
                step="1",
            ),
            FormField("access_notes", "Access notes", "textarea"),
            FormField("hgv_notes", "HGV notes", "textarea"),
            FormField("receiving_notes", "Receiving notes", "textarea"),
            ACTIVE,
        ),
        ("name", "location_type", "city", "country_code", "timezone", "active"),
    ),
    EntityDefinition(
        "tent-families",
        "Tent family",
        "Tent families",
        "Tent and equipment",
        TentFamily,
        TentFamilyData,
        (
            FormField("name", "Name", required=True),
            FormField("description", "Description", "textarea"),
            FormField(
                "pole_equipment_type_id",
                "Pole equipment type",
                "select",
                option_model=EquipmentType,
                option_label="code",
                help_text="Which equipment type fulfils this family's derived pole requirement "
                "(e.g. P). Leave blank until known — no poles will be derived without it.",
            ),
            FormField(
                "pole_count_multiplier",
                "Pole count multiplier",
                "number",
                required=True,
                default=2,
                step="1",
            ),
            FormField(
                "pole_count_offset",
                "Pole count offset",
                "number",
                required=True,
                default=-2,
                step="1",
                help_text="poles = sections × multiplier + offset. Kayam's known formula is "
                "sections×2−2 (multiplier=2, offset=-2).",
            ),
            FormField(
                "default_build_hours",
                "Default build hours",
                "number",
                required=True,
                default=0,
                step="0.25",
            ),
            FormField(
                "default_strike_hours",
                "Default strike hours",
                "number",
                required=True,
                default=0,
                step="0.25",
            ),
            FormField("minimum_crew", "Minimum crew", "number", required=True, default=0),
            FormField("preferred_crew", "Preferred crew", "number", required=True, default=0),
            ACTIVE,
        ),
        ("name", "pole_equipment_type_id", "minimum_crew", "preferred_crew", "active"),
    ),
    EntityDefinition(
        "equipment-types",
        "Equipment type",
        "Equipment types",
        "Tent and equipment",
        EquipmentType,
        EquipmentTypeData,
        (
            FormField(
                "code",
                "Code",
                required=True,
                help_text='Case-sensitive — "M" (20m middle) and "m" (15m middle) are different '
                "types.",
            ),
            FormField("name", "Name", required=True),
            FormField(
                "category",
                "Category",
                required=True,
                help_text='"section" = bookable in a tent sequence, "pole" = derived from '
                'section count, "linked" = implied by another type, "ancillary" = tracked '
                "independently.",
            ),
            FormField("tent_family_id", "Tent family", "select", option_model=TentFamily),
            FormField(
                "pack_size",
                "Pack size",
                "number",
                required=True,
                default=1,
                step="1",
                help_text="Physical units per tracked asset (e.g. 2 for a pole type sold/tracked "
                "as a pair).",
            ),
            FormField(
                "tracking_mode",
                "Tracking mode",
                "select",
                required=True,
                default=TrackingMode.INDIVIDUAL.value,
                choices=enum_choices(TrackingMode),
            ),
            FormField(
                "section_capacity_units",
                "Section capacity units",
                "number",
                required=True,
                default=0,
                step=CAPACITY_STEP,
            ),
            FormField(
                "pole_capacity_units",
                "Pole capacity units",
                "number",
                required=True,
                default=0,
                step=CAPACITY_STEP,
            ),
            FormField(
                "ancillary_capacity_units",
                "Ancillary capacity units",
                "number",
                required=True,
                default=0,
                step=CAPACITY_STEP,
            ),
            FormField("weight_kg", "Weight (kg)", "number", required=True, default=0, step="0.01"),
            FormField(
                "default_build_stage",
                "Default build stage",
                "select",
                required=True,
                default=BuildStage.COMPLETION_AND_ANCILLARY.value,
                choices=enum_choices(BuildStage),
            ),
            FormField(
                "maintenance_interval_days",
                "Maintenance interval (days)",
                "number",
                step="1",
            ),
            ACTIVE,
            NOTES,
        ),
        ("code", "name", "category", "tracking_mode", "active"),
    ),
    EntityDefinition(
        "equipment-assets",
        "Equipment asset",
        "Equipment assets",
        "Tent and equipment",
        EquipmentAsset,
        EquipmentAssetData,
        (
            FormField("asset_code", "Asset code", required=True),
            FormField(
                "equipment_type_id",
                "Equipment type",
                "select",
                required=True,
                option_model=EquipmentType,
                option_label="code",
            ),
            FormField("variant", "Variant"),
            FormField("generation", "Generation"),
            FormField(
                "initial_location_id",
                "Initial location",
                "select",
                option_model=Location,
            ),
            FormField("current_status", "Current status", required=True, default="available"),
            FormField("serviceable", "Serviceable", "checkbox", default=True),
            FormField("commissioned_date", "Commissioned date", "date"),
            FormField("retired_date", "Retired date", "date"),
            FormField("replacement_value", "Replacement value", "number", step=MONEY_STEP),
            ACTIVE,
            NOTES,
        ),
        ("asset_code", "equipment_type_id", "current_status", "serviceable", "active"),
    ),
    EntityDefinition(
        "equipment-links",
        "Linked equipment",
        "Linked equipment",
        "Tent and equipment",
        EquipmentLink,
        EquipmentLinkData,
        (
            FormField(
                "parent_equipment_type_id",
                "Parent (booked) equipment type",
                "select",
                required=True,
                option_model=EquipmentType,
                option_label="code",
            ),
            FormField(
                "child_equipment_type_id",
                "Linked (derived) equipment type",
                "select",
                required=True,
                option_model=EquipmentType,
                option_label="code",
            ),
            FormField(
                "quantity_per_parent",
                "Quantity per parent",
                "number",
                required=True,
                step="1",
                help_text="e.g. an M implies 2 of this linked type.",
            ),
            NOTES,
        ),
        ("parent_equipment_type_id", "child_equipment_type_id", "quantity_per_parent"),
    ),
    EntityDefinition(
        "crew-roles",
        "Crew role",
        "Crew roles",
        "Crew",
        CrewRole,
        CrewRoleData,
        (
            FormField("name", "Name", required=True),
            FormField("is_default", "Default for new crew members", "checkbox"),
            ACTIVE,
        ),
        ("name", "is_default", "active"),
    ),
    EntityDefinition(
        "crew-employment-types",
        "Employment type",
        "Employment types",
        "Crew",
        CrewEmploymentType,
        CrewEmploymentTypeData,
        (
            FormField("name", "Name", required=True),
            FormField("is_default", "Default for new crew members", "checkbox"),
            ACTIVE,
        ),
        ("name", "is_default", "active"),
    ),
    EntityDefinition(
        "crew-members",
        "Crew member",
        "Crew members",
        "Crew",
        CrewMember,
        CrewMemberData,
        (
            FormField("name", "Name", required=True),
            FormField("role_id", "Role", "select", required=True, option_model=CrewRole),
            FormField(
                "employment_type_id",
                "Employment type",
                "select",
                required=True,
                option_model=CrewEmploymentType,
            ),
            FormField(
                "hourly_cost", "Hourly cost", "number", required=True, default=0, step=MONEY_STEP
            ),
            FormField(
                "overtime_hourly_cost",
                "Overtime hourly cost",
                "number",
                required=True,
                default=0,
                step=MONEY_STEP,
            ),
            FormField(
                "travel_hourly_cost",
                "Travel hourly cost",
                "number",
                required=True,
                default=0,
                step=MONEY_STEP,
            ),
            FormField(
                "daily_allowance",
                "Daily allowance",
                "number",
                required=True,
                default=0,
                step=MONEY_STEP,
            ),
            FormField("can_drive_van", "Can drive van", "checkbox"),
            FormField("can_drive_hgv", "Can drive HGV", "checkbox"),
            FormField("skills", "Skills", "textarea"),
            FormField("home_location_id", "Home location", "select", option_model=Location),
            ACTIVE,
            NOTES,
        ),
        ("name", "role_id", "employment_type_id", "can_drive_van", "can_drive_hgv", "active"),
    ),
    EntityDefinition(
        "tentmasters",
        "Tentmaster",
        "Tentmasters",
        "Crew",
        Tentmaster,
        TentmasterData,
        (
            FormField("name", "Name", required=True),
            FormField(
                "lead_crew_member_id",
                "Lead crew member",
                "select",
                option_model=CrewMember,
            ),
            FormField("home_location_id", "Home location", "select", option_model=Location),
            FormField(
                "default_van_id",
                "Default van",
                "select",
                option_model=Van,
                option_label="registration_or_name",
            ),
            ACTIVE,
            NOTES,
        ),
        ("name", "lead_crew_member_id", "home_location_id", "default_van_id", "active"),
    ),
    EntityDefinition(
        "tentmaster-memberships",
        "Tentmaster membership",
        "Tentmaster memberships",
        "Crew",
        TentmasterMembership,
        TentmasterMembershipData,
        (
            FormField(
                "tentmaster_id",
                "Tentmaster",
                "select",
                required=True,
                option_model=Tentmaster,
            ),
            FormField(
                "crew_member_id",
                "Crew member",
                "select",
                required=True,
                option_model=CrewMember,
            ),
            FormField("start_at", "Start date", "date", required=True),
            FormField(
                "end_at",
                "End date",
                "date",
                help_text="First day no longer active — leave blank if ongoing. A crew member "
                "can start with another Tentmaster on this same date.",
            ),
            FormField("is_default", "Default team", "checkbox", default=True),
            NOTES,
        ),
        ("crew_member_id", "tentmaster_id", "start_at", "end_at", "is_default"),
    ),
    EntityDefinition(
        "crew-availability",
        "Crew availability",
        "Crew availability",
        "Crew",
        CrewAvailability,
        CrewAvailabilityData,
        (
            FormField(
                "crew_member_id",
                "Crew member",
                "select",
                required=True,
                option_model=CrewMember,
            ),
            FormField("start_at", "Start date", "date", required=True),
            FormField("end_at", "End date", "date", required=True),
            FormField(
                "status",
                "Status",
                "select",
                required=True,
                choices=enum_choices(CrewAvailabilityStatus),
            ),
            NOTES,
        ),
        ("crew_member_id", "start_at", "end_at", "status"),
        hidden=True,
    ),
    EntityDefinition(
        "crew-availability-windows",
        "Availability window",
        "Availability windows",
        "Crew",
        CrewAvailabilityWindow,
        CrewAvailabilityWindowData,
        (
            FormField(
                "crew_member_id",
                "Crew member",
                "select",
                required=True,
                option_model=CrewMember,
            ),
            FormField(
                "start_at",
                "Available from",
                "date",
                required=True,
                help_text="Multiple windows are allowed per crew member. If a crew member has "
                "no windows at all, they are treated as always available.",
            ),
            FormField("end_at", "Available until", "date", help_text="Leave blank if ongoing."),
            NOTES,
        ),
        ("crew_member_id", "start_at", "end_at"),
        hidden=True,
    ),
    EntityDefinition(
        "lorry-types",
        "Lorry type",
        "Lorry types",
        "Vehicles and suppliers",
        LorryType,
        LorryTypeData,
        (
            FormField("name", "Name", required=True),
            FormField(
                "section_capacity_units",
                "Section capacity units",
                "number",
                required=True,
                default=0,
                step=CAPACITY_STEP,
            ),
            FormField(
                "pole_capacity_units",
                "Pole capacity units",
                "number",
                required=True,
                default=0,
                step=CAPACITY_STEP,
            ),
            FormField(
                "ancillary_capacity_units",
                "Ancillary capacity units",
                "number",
                required=True,
                default=0,
                step=CAPACITY_STEP,
            ),
            FormField(
                "payload_kg", "Payload (kg)", "number", required=True, default=0, step="0.01"
            ),
            FormField(
                "passenger_capacity", "Passenger capacity", "number", required=True, default=0
            ),
            FormField(
                "default_cost_per_km",
                "Default cost per km",
                "number",
                required=True,
                default=0,
                step=MONEY_STEP,
            ),
            FormField(
                "minimum_load_cost",
                "Minimum load cost",
                "number",
                required=True,
                default=0,
                step=MONEY_STEP,
            ),
            ACTIVE,
            NOTES,
        ),
        (
            "name",
            "section_capacity_units",
            "pole_capacity_units",
            "ancillary_capacity_units",
            "payload_kg",
            "active",
        ),
    ),
    EntityDefinition(
        "hauliers",
        "Haulier",
        "Hauliers",
        "Vehicles and suppliers",
        Haulier,
        HaulierData,
        (
            FormField("name", "Name", required=True),
            FormField("contact_name", "Contact name"),
            FormField("email", "Email", "email"),
            FormField("phone", "Phone"),
            FormField("currency", "Currency", required=True, default="GBP"),
            FormField(
                "default_cost_per_km",
                "Default cost per km",
                "number",
                required=True,
                default=0,
                step=MONEY_STEP,
            ),
            FormField(
                "minimum_load_cost",
                "Minimum load cost",
                "number",
                required=True,
                default=0,
                step=MONEY_STEP,
            ),
            FormField(
                "waiting_hourly_cost",
                "Waiting hourly cost",
                "number",
                required=True,
                default=0,
                step=MONEY_STEP,
            ),
            FormField(
                "fuel_surcharge_percent",
                "Fuel surcharge (%)",
                "number",
                required=True,
                default=0,
                step="0.01",
            ),
            ACTIVE,
            NOTES,
        ),
        ("name", "contact_name", "currency", "active"),
    ),
    EntityDefinition(
        "vans",
        "Van",
        "Vans",
        "Vehicles and suppliers",
        Van,
        VanData,
        (
            FormField("registration_or_name", "Registration or name", required=True),
            FormField(
                "passenger_capacity", "Passenger capacity", "number", required=True, default=0
            ),
            FormField(
                "cargo_capacity_units",
                "Cargo capacity units",
                "number",
                required=True,
                default=0,
                step=CAPACITY_STEP,
            ),
            FormField(
                "home_location_id",
                "Home location",
                "select",
                required=True,
                option_model=Location,
            ),
            FormField(
                "ownership_type",
                "Ownership type",
                "select",
                required=True,
                default=OwnershipType.OWNED.value,
                choices=enum_choices(OwnershipType),
            ),
            FormField(
                "cost_per_km", "Cost per km", "number", required=True, default=0, step=MONEY_STEP
            ),
            ACTIVE,
            NOTES,
        ),
        (
            "registration_or_name",
            "passenger_capacity",
            "home_location_id",
            "ownership_type",
            "active",
        ),
    ),
    EntityDefinition(
        "lorries",
        "Lorry",
        "Lorries",
        "Vehicles and suppliers",
        Lorry,
        LorryData,
        (
            FormField("registration_or_name", "Registration or name", required=True),
            FormField(
                "lorry_type_id",
                "Lorry type",
                "select",
                required=True,
                option_model=LorryType,
            ),
            FormField("haulier_id", "Haulier", "select", option_model=Haulier),
            FormField(
                "ownership_type",
                "Ownership type",
                "select",
                required=True,
                default=OwnershipType.OWNED.value,
                choices=enum_choices(OwnershipType),
            ),
            FormField("home_location_id", "Home location", "select", option_model=Location),
            ACTIVE,
            NOTES,
        ),
        ("registration_or_name", "lorry_type_id", "haulier_id", "ownership_type", "active"),
    ),
)

ENTITY_BY_SLUG = {definition.slug: definition for definition in ENTITY_DEFINITIONS}


def grouped_entities() -> dict[str, list[EntityDefinition]]:
    groups: dict[str, list[EntityDefinition]] = {}
    for definition in ENTITY_DEFINITIONS:
        if definition.hidden:
            continue
        groups.setdefault(definition.group, []).append(definition)
    return groups
