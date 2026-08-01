from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_database_session_connects(test_engine: Engine) -> None:
    with test_engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1


def test_foundation_migration_upgrades_clean_database(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config(PROJECT_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    migrated_engine = create_engine(f"sqlite:///{database_path}")
    try:
        assert set(inspect(migrated_engine).get_table_names()) == {
            "alembic_version",
            "audit_logs",
            "crew_availability",
            "crew_activities",
            "crew_assignments",
            "crew_journey_legs",
            "crew_members",
            "crew_movement_passengers",
            "crew_movements",
            "equipment_assets",
            "equipment_assignments",
            "equipment_compatibility",
            "equipment_movements",
            "equipment_types",
            "hauliers",
            "job_equipment_requirements",
            "job_phases",
            "job_tent_requirements",
            "jobs",
            "locations",
            "load_cost_allocations",
            "load_items",
            "loads",
            "lorries",
            "lorry_types",
            "route_cache",
            "supplier_invoices",
            "tent_configuration_requirements",
            "tent_configurations",
            "tent_families",
            "tentmaster_memberships",
            "tentmasters",
            "vans",
        }
        with migrated_engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision == "73de560fde26"
    finally:
        migrated_engine.dispose()
