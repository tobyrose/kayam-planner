"""SQLAlchemy models available to the application and Alembic."""

from app.models.administration import (
    CrewAvailability,
    CrewAvailabilityWindow,
    CrewEmploymentType,
    CrewMember,
    CrewRole,
    EquipmentAsset,
    EquipmentLink,
    EquipmentType,
    Haulier,
    Location,
    Lorry,
    LorryType,
    TentFamily,
    Tentmaster,
    TentmasterMembership,
    Van,
)
from app.models.audit import AuditLog
from app.models.costing import LoadCostAllocation, SupplierInvoice
from app.models.crew_movements import CrewJourneyLeg, CrewMovement, CrewMovementPassenger
from app.models.crew_planning import CrewActivity
from app.models.equipment_planning import EquipmentAssignment, EquipmentCompatibility
from app.models.jobs import (
    Job,
    JobEquipmentRequirement,
    JobPhase,
    JobTentRequirement,
    JobTentSection,
    LocalCrewBooking,
)
from app.models.logistics import EquipmentMovement, Load, LoadItem, RouteCache

__all__ = [
    "CrewAvailability",
    "CrewAvailabilityWindow",
    "CrewEmploymentType",
    "CrewRole",
    "AuditLog",
    "CrewActivity",
    "CrewMember",
    "CrewJourneyLeg",
    "CrewMovement",
    "CrewMovementPassenger",
    "EquipmentAsset",
    "EquipmentAssignment",
    "EquipmentCompatibility",
    "EquipmentLink",
    "EquipmentType",
    "EquipmentMovement",
    "Haulier",
    "Job",
    "JobEquipmentRequirement",
    "JobPhase",
    "JobTentRequirement",
    "JobTentSection",
    "Location",
    "LocalCrewBooking",
    "Load",
    "LoadCostAllocation",
    "LoadItem",
    "RouteCache",
    "Lorry",
    "LorryType",
    "SupplierInvoice",
    "TentFamily",
    "Tentmaster",
    "TentmasterMembership",
    "Van",
]
