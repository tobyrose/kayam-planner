"""SQLAlchemy models available to the application and Alembic."""

from app.models.administration import (
    CrewAvailability,
    CrewMember,
    EquipmentAsset,
    EquipmentType,
    Haulier,
    Location,
    Lorry,
    LorryType,
    TentConfiguration,
    TentConfigurationRequirement,
    TentFamily,
    Tentmaster,
    TentmasterMembership,
    Van,
)
from app.models.audit import AuditLog
from app.models.costing import LoadCostAllocation, SupplierInvoice
from app.models.crew_movements import CrewJourneyLeg, CrewMovement, CrewMovementPassenger
from app.models.crew_planning import CrewActivity, CrewAssignment
from app.models.equipment_planning import EquipmentAssignment, EquipmentCompatibility
from app.models.jobs import Job, JobEquipmentRequirement, JobPhase, JobTentRequirement
from app.models.logistics import EquipmentMovement, Load, LoadItem, RouteCache

__all__ = [
    "CrewAvailability",
    "AuditLog",
    "CrewActivity",
    "CrewAssignment",
    "CrewMember",
    "CrewJourneyLeg",
    "CrewMovement",
    "CrewMovementPassenger",
    "EquipmentAsset",
    "EquipmentAssignment",
    "EquipmentCompatibility",
    "EquipmentType",
    "EquipmentMovement",
    "Haulier",
    "Job",
    "JobEquipmentRequirement",
    "JobPhase",
    "JobTentRequirement",
    "Location",
    "Load",
    "LoadCostAllocation",
    "LoadItem",
    "RouteCache",
    "Lorry",
    "LorryType",
    "TentConfiguration",
    "SupplierInvoice",
    "TentConfigurationRequirement",
    "TentFamily",
    "Tentmaster",
    "TentmasterMembership",
    "Van",
]
