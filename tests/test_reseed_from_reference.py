from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.reseed_from_reference import (
    clear_operational_data,
    reseed_jobs,
    reseed_stock,
)
from app.commands.seed import seed_development_data
from app.models.administration import (
    CrewMember,
    EquipmentAsset,
    EquipmentType,
    Location,
    LocationType,
    Tentmaster,
)
from app.models.jobs import Job, JobPhase


def test_reseed_populates_jobs_and_stock_and_preserves_reference_data(session: Session) -> None:
    seed_development_data(session, include_operational_demo=True)
    crew_count_before = len(session.scalars(select(CrewMember)).all())
    tentmaster_count_before = len(session.scalars(select(Tentmaster)).all())
    equipment_type_count_before = len(session.scalars(select(EquipmentType)).all())
    assert crew_count_before > 0 and tentmaster_count_before > 0

    clear_operational_data(session)
    assert session.scalars(select(Job)).all() == []
    assert session.scalars(select(EquipmentAsset)).all() == []
    # Reference data untouched by the clear step.
    assert len(session.scalars(select(CrewMember)).all()) == crew_count_before
    assert len(session.scalars(select(Tentmaster)).all()) == tentmaster_count_before
    assert len(session.scalars(select(EquipmentType)).all()) == equipment_type_count_before

    yard = session.scalar(select(Location).where(Location.location_type == LocationType.YARD))
    assert yard is not None
    assets_created = reseed_stock(session, yard)
    assert assets_created > 0
    assert len(session.scalars(select(EquipmentAsset)).all()) == assets_created

    jobs_created = reseed_jobs(session)
    # 9 CSV rows, but two share the JOB name SOLIDAYS → 8 jobs (SOLIDAYS has two tents).
    assert jobs_created == 8

    jobs = session.scalars(select(Job)).all()
    assert {job.job_code for job in jobs} >= {"CATALYST", "ROSKILDE", "SOLIDAYS"}
    assert "SOLIDAYS-2" not in {job.job_code for job in jobs}
    # Every phase lands unassigned — no Tentmaster attached by the reseed.
    phases = session.scalars(select(JobPhase)).all()
    assert phases
    assert all(phase.tentmaster_id is None for phase in phases)

    silverstone = next(job for job in jobs if job.job_code == "SILVERSTONE")
    assert "T" in silverstone.tent_requirements[0].sequence_code

    # A job with a valid sequence got sections, derived poles, and a linked-equipment cascade.
    catalyst = next(job for job in jobs if job.job_code == "CATALYST")
    assert len(catalyst.tent_requirements) == 1
    assert catalyst.tent_requirements[0].sequence_code == "VOEVVVVOE"

    # SOLIDAYS is one job with two tents (two CSV rows, same JOB name), not two jobs.
    solidays = next(job for job in jobs if job.job_code == "SOLIDAYS")
    assert len(solidays.tent_requirements) == 2
    tent_labels = {tent.custom_name for tent in solidays.tent_requirements}
    assert tent_labels == {"6 K SC", "4 Siam"}
    sequences = {tent.sequence_code for tent in solidays.tent_requirements}
    assert sequences == {"KMmSC", "sms"}


def test_reseed_is_safely_rerunnable(session: Session) -> None:
    """Re-running the reseed (e.g. after fixing a source-data typo) must not collide on the
    venue Locations created by the previous run."""
    seed_development_data(session, include_operational_demo=True)
    yard = session.scalar(select(Location).where(Location.location_type == LocationType.YARD))
    assert yard is not None

    clear_operational_data(session)
    reseed_stock(session, yard)
    first_run_jobs = reseed_jobs(session)

    session.expire_all()
    clear_operational_data(session)
    reseed_stock(session, yard)
    second_run_jobs = reseed_jobs(session)

    assert first_run_jobs == second_run_jobs == 8
    assert len(session.scalars(select(Job)).all()) == 8


def test_reseed_maps_stock_codes_by_prefix_correctly(session: Session) -> None:
    seed_development_data(session, include_operational_demo=True)
    clear_operational_data(session)
    yard = session.scalar(select(Location).where(Location.location_type == LocationType.YARD))
    assert yard is not None
    reseed_stock(session, yard)

    def type_code_for(asset_code: str) -> str:
        asset = session.scalar(
            select(EquipmentAsset).where(EquipmentAsset.asset_code == asset_code)
        )
        assert asset is not None
        return asset.equipment_type.code

    assert type_code_for("K1") == "K"
    assert type_code_for("M21") == "M"
    assert type_code_for("m5") == "m"
    assert type_code_for("s3") == "s"
    assert type_code_for("sc1") == "SC"
    assert type_code_for("VOE1") == "VOE"
    assert type_code_for("VNE1") == "VNE"
    assert type_code_for("Vb1") == "VB"
    assert type_code_for("V1") == "V"
