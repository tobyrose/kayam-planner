from __future__ import annotations

import argparse
from pathlib import Path

from app.services.system import backup_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent Kayam SQLite backup")
    parser.add_argument("destination", nargs="?", default="backups", type=Path)
    args = parser.parse_args()
    destination = backup_database(args.destination)
    print(f"Backup created: {destination}")


if __name__ == "__main__":
    main()
