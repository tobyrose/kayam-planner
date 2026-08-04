"""Compare job loadable requirements (sections + poles) against load contents to the site."""

from __future__ import annotations

from collections import defaultdict

from app.models.jobs import Job
from app.models.logistics import Load

# What must ride on lorries for a job to be considered covered.
LOADABLE_CATEGORIES = frozenset({"section", "pole"})


def loadable_requirements(job: Job) -> dict[str, int]:
    """Required section + pole quantities by type code (linked kit is implied, not packed here)."""
    required: dict[str, int] = defaultdict(int)
    for requirement in job.equipment_requirements:
        if requirement.equipment_type.category not in LOADABLE_CATEGORIES:
            continue
        required[requirement.equipment_type.code] += int(requirement.quantity_required)
    return dict(required)


# Back-compat aliases used by existing callers
def section_requirements(job: Job) -> dict[str, int]:
    return loadable_requirements(job)


def loadable_delivered(loads: list[Load]) -> dict[str, int]:
    delivered: dict[str, int] = defaultdict(int)
    for load in loads:
        for item in load.items:
            equipment_type = item.resolved_type
            if equipment_type.category not in LOADABLE_CATEGORIES:
                continue
            delivered[equipment_type.code] += int(item.quantity)
    return dict(delivered)


def section_delivered(loads: list[Load]) -> dict[str, int]:
    return loadable_delivered(loads)


def section_shortfalls(job: Job, loads: list[Load]) -> dict[str, int]:
    """How many of each loadable type are still short after counting loads to the job."""
    required = loadable_requirements(job)
    delivered = loadable_delivered(loads)
    short: dict[str, int] = {}
    for code, need in required.items():
        have = delivered.get(code, 0)
        if have < need:
            short[code] = need - have
    return short


def job_has_section_shortfall(job: Job, loads: list[Load]) -> bool:
    return bool(section_shortfalls(job, loads))


def format_section_shortfall(shortfalls: dict[str, int]) -> str:
    if not shortfalls:
        return ""
    parts = [f"{code}×{qty}" for code, qty in sorted(shortfalls.items())]
    return "Kit short: " + ", ".join(parts)
