from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from app.database import SessionLocal
from app.services.system import write_core_export


def main() -> None:
    parser = argparse.ArgumentParser(description="Export core Kayam planning data as JSON")
    parser.add_argument("destination", nargs="?", type=Path)
    args = parser.parse_args()
    destination = args.destination or Path("exports") / (
        f"kayam-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    with SessionLocal() as session:
        write_core_export(session, destination)
    print(f"JSON export created: {destination}")


if __name__ == "__main__":
    main()
