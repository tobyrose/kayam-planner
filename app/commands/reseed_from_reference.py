"""Clear operational/demo data and reseed jobs from the real reference CSV and stock list.

Kept untouched: the equipment taxonomy (`EquipmentType`/`TentFamily`/`EquipmentLink`), crew and
Tentmaster reference data, "Oxford Yard", and other admin/logistics reference tables
(`Lorry`/`LorryType`/`Haulier`/`Van`). Audit log rows are left in place too (historical record).

Cleared: every `EquipmentMovement` (cascades `Load`/`LoadItem`), every `CrewMovement` (cascades
legs/passengers), every `Job` (cascades phases/tent requirements/equipment requirements/
assignments/local crew bookings), every `EquipmentAsset` (the old demo stock), and every
`Location` except the Yard and the three demo-only sites — i.e. every venue `Location`, whether
from `reference/kay_seed_jobs.csv` or an earlier reseed run, since only the reseed ever creates
venue Locations.

Reseeded: one `EquipmentAsset` per line in `reference/kay_seed_stock.txt`, mapped onto the
existing taxonomy by code prefix; one `Job` per distinct JOB name in
`reference/kay_seed_jobs.csv` (multiple CSV rows with the same name are extra tents on that job —
e.g. both SOLIDAYS rows → one SOLIDAYS job with two tent requirements), plus one `Location` per
distinct venue. Every job lands with no Tentmaster on any phase (Unassigned/Quoted) —
deliberately, so allocation can be tried from a clean slate. No loads or equipment assignments
are seeded.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.administration import EquipmentAsset, EquipmentType, Location, LocationType
from app.models.costing import LoadCostAllocation
from app.models.crew_movements import CrewMovement
from app.models.jobs import CommercialStatus, Job, PlanningStatus
from app.models.logistics import EquipmentMovement
from app.services.jobs import JobError, JobService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = PROJECT_ROOT / "reference" / "kay_seed_jobs.csv"
STOCK_PATH = PROJECT_ROOT / "reference" / "kay_seed_stock.txt"

LONDON = ZoneInfo("Europe/London")

DEMO_SITE_LOCATIONS = ("Roskilde Demo Site", "Scotland Demo Site", "UK Demo Event Site")
RESEED_LOCATION_MARKER = (
    "Seeded from reference/kay_seed_jobs.csv — safe to delete and re-run the reseed command."
)
# Every Location that survives a clear is either the Yard (location_type=YARD, kept everywhere) or
# one of the three demo-only sites above. Any other Location was created by a reseed run — this
# turn's or an earlier one's — and is always safe to delete, regardless of whether it happens to
# carry RESEED_LOCATION_MARKER (older reseed runs, before the marker existed, won't).

# Longest/most-specific prefix first, so e.g. "VNE"/"Vb"/"sc" match before the bare "V"/"s" they'd
# otherwise collide with. Matches the real letter-code taxonomy from D030.
STOCK_PREFIXES: tuple[tuple[str, str], ...] = (
    ("VNE", "VNE"),
    ("VOE", "VOE"),
    ("Vb", "VB"),
    ("sc", "SC"),
    ("ad", "AD"),
    ("ct", "CT"),
    ("sb", "SB"),
    ("rd", "RD"),
    ("K", "K"),
    ("M", "M"),
    ("m", "m"),
    ("s", "s"),
    ("T", "T"),
    ("P", "P"),
    ("X", "X"),
    ("V", "V"),
)

# Hand-supplied coordinates (owner-provided, not geocoded here — see DECISIONS.md D037).
GEOCODED: dict[str, tuple[Decimal, Decimal]] = {
    "CATALYST": (Decimal("52.646735"), Decimal("1.1776174")),
    "MAGNITUDE/SU SCOTLAND": (Decimal("56.1850715"), Decimal("-3.5742884")),
    "READING": (Decimal("51.4654162"), Decimal("-0.7915039")),
    "ROSKILDE": (Decimal("55.621642"), Decimal("12.071222")),
    "SHAMBALA": (Decimal("52.409374"), Decimal("-0.918940")),
    "SILVERSTONE": (Decimal("52.073676"), Decimal("-1.021653")),
    "SOLIDAYS": (Decimal("48.858741"), Decimal("2.229825")),
    "WILD FIRES": (Decimal("50.888654"), Decimal("-0.406953")),
}


def _equipment_type_for_stock_code(session: Session, stock_code: str) -> EquipmentType | None:
    for prefix, type_code in STOCK_PREFIXES:
        if stock_code.startswith(prefix):
            return session.scalar(select(EquipmentType).where(EquipmentType.code == type_code))
    return None


def _country_and_timezone(address: str) -> tuple[str, str]:
    if "Denmark" in address:
        return "DK", "Europe/Copenhagen"
    if "France" in address:
        return "FR", "Europe/Paris"
    return "GB", "Europe/London"


def _parse_datetime(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%d/%m/%Y %H:%M").replace(tzinfo=LONDON)


def clear_operational_data(session: Session) -> None:
    # LoadCostAllocation references both Load and Job without ON DELETE CASCADE, so it must go
    # first.
    session.execute(delete(LoadCostAllocation))
    session.execute(delete(EquipmentMovement))
    session.execute(delete(CrewMovement))
    session.execute(delete(Job))
    session.execute(delete(EquipmentAsset))
    session.execute(
        delete(Location).where(
            Location.location_type != LocationType.YARD,
            Location.name.notin_(DEMO_SITE_LOCATIONS),
        )
    )
    session.commit()


def reseed_stock(session: Session, yard: Location) -> int:
    created = 0
    unmatched: list[str] = []
    for line in STOCK_PATH.read_text().splitlines():
        code = line.strip()
        if not code:
            continue
        equipment_type = _equipment_type_for_stock_code(session, code)
        if equipment_type is None:
            unmatched.append(code)
            continue
        session.add(
            EquipmentAsset(
                asset_code=code,
                equipment_type_id=equipment_type.id,
                initial_location_id=yard.id,
            )
        )
        created += 1
    session.commit()
    if unmatched:
        print(f"WARNING: could not map these stock codes to a known equipment type: {unmatched}")
    return created


def reseed_jobs(session: Session) -> int:
    """One Job per distinct JOB name; extra CSV rows with the same name add more tents."""
    job_service = JobService(session)
    jobs_by_slug: dict[str, Job] = {}
    locations_by_venue: dict[str, Location] = {}
    warnings: list[str] = []
    created = 0
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = row["JOB"].strip()
            slug = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")

            address = row["SITE ADDRESS"].strip()
            venue = address.split(",")[0].strip()
            # Same venue address segment → shared Location (e.g. both SOLIDAYS tents at Longchamp).
            location = locations_by_venue.get(venue)
            if location is None:
                country_code, timezone = _country_and_timezone(address)
                lat_lon = GEOCODED.get(name)
                location = Location(
                    name=venue,
                    location_type=LocationType.SITE,
                    address_line_1=address,
                    country_code=country_code,
                    timezone=timezone,
                    latitude=lat_lon[0] if lat_lon else None,
                    longitude=lat_lon[1] if lat_lon else None,
                    access_notes=RESEED_LOCATION_MARKER,
                )
                session.add(location)
                session.flush()
                locations_by_venue[venue] = location

            job = jobs_by_slug.get(slug)
            if job is None:
                job = Job(
                    job_code=slug,
                    name=name,
                    customer_name="TBC",
                    location_id=location.id,
                    commercial_status=CommercialStatus.QUOTED,
                    planning_status=PlanningStatus.NOT_PLANNED,
                )
                session.add(job)
                session.flush()
                jobs_by_slug[slug] = job
                created += 1
            elif job.location_id != location.id:
                warnings.append(
                    f"{slug}: CSV row points at a different venue than the first row for this "
                    f"job name — tent still added on job {slug} at location id {job.location_id}."
                )

            try:
                up_at = _parse_datetime(row["Up"])
                down_at = _parse_datetime(row["Down"])
                if down_at <= up_at:
                    raise JobError(
                        f"Down ({down_at:%d %b %Y %H:%M}) is not after "
                        f"Up ({up_at:%d %b %Y %H:%M}) — check the source CSV row"
                    )
                job_service.add_tent_requirement(
                    job.id,
                    {
                        "sequence": row["Sections"].strip(),
                        "quantity": 1,
                        "custom_name": row["Label"].strip() or None,
                        "contracted_up_at": up_at,
                        "contracted_down_at": down_at,
                    },
                )
            except JobError as error:
                # Nothing tent-related was added before this fires (either our own date check,
                # raised before calling add_tent_requirement, or that method's own up-front
                # validation) — the job/location already flushed above are still good to keep.
                session.commit()
                warnings.append(
                    f"{slug}: {error} — tent not added; fix the source CSV row and re-run."
                )
    if warnings:
        print("WARNINGS (jobs created but need manual attention):")
        for warning in warnings:
            print(f"  - {warning}")
    return created


def main() -> None:
    with SessionLocal() as session:
        yard = session.scalar(select(Location).where(Location.location_type == LocationType.YARD))
        if yard is None:
            raise RuntimeError("No Yard location found — seed administration data first")
        clear_operational_data(session)
        assets_created = reseed_stock(session, yard)
        jobs_created = reseed_jobs(session)
    print(f"Reseed complete: {assets_created} equipment assets, {jobs_created} jobs.")


if __name__ == "__main__":
    main()
