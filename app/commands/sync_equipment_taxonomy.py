"""Apply new/updated linked-equipment taxonomy (types + `EquipmentLink` ratios) to an existing
database without touching jobs, crew, or any other operational data.

Safe to re-run: every insert goes through `seed.get_or_create`, so rows that already exist by
code (or by parent/child pair for links) are left untouched. Intended for pushing incremental
`LINKED_PARTS_MATRIX` updates in `app/commands/seed.py` (e.g. a corrected quantity from the
owner) onto the live `instance/kayam.db` after the initial taxonomy was already seeded, since
`kayam-seed`'s `main()` also seeds demo jobs/locations that must not be reapplied there.
"""

from __future__ import annotations

from sqlalchemy import select

from app.commands.seed import _ensure_linked_parts, _ensure_loading_points
from app.database import SessionLocal
from app.models.administration import EquipmentType


def main() -> None:
    with SessionLocal() as session:
        equipment_types = {
            equipment_type.code: equipment_type
            for equipment_type in session.scalars(select(EquipmentType))
        }
        if "K" not in equipment_types:
            raise RuntimeError("No equipment taxonomy found — seed administration data first")
        created = _ensure_linked_parts(session, equipment_types)
        points_updated = _ensure_loading_points(session)
        session.commit()
    print(
        f"Equipment taxonomy sync complete: {created} new records, "
        f"{points_updated} loading-point updates."
    )


if __name__ == "__main__":
    main()
