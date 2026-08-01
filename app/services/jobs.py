from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.administration import BuildStage, TentConfiguration
from app.models.jobs import (
    CommercialStatus,
    Job,
    JobEquipmentRequirement,
    JobPhase,
    JobTentRequirement,
    PhaseType,
    PlanningStatus,
    RecordSource,
    RequirementSource,
    RequirementStatus,
)
from app.schemas.jobs import JobData, JobPhaseData, JobTentRequirementData


class JobError(Exception):
    pass


class JobNotFoundError(JobError):
    pass


class JobConflictError(JobError):
    pass


COMMERCIAL_TRANSITIONS: dict[CommercialStatus, set[CommercialStatus]] = {
    CommercialStatus.ENQUIRY: {
        CommercialStatus.QUOTE_IN_PREPARATION,
        CommercialStatus.QUOTED,
        CommercialStatus.CANCELLED,
    },
    CommercialStatus.QUOTE_IN_PREPARATION: {
        CommercialStatus.QUOTED,
        CommercialStatus.CANCELLED,
    },
    CommercialStatus.QUOTED: {
        CommercialStatus.DEPOSIT_REQUESTED,
        CommercialStatus.DEPOSIT_RECEIVED,
        CommercialStatus.CONFIRMED,
        CommercialStatus.CANCELLED,
    },
    CommercialStatus.DEPOSIT_REQUESTED: {
        CommercialStatus.DEPOSIT_RECEIVED,
        CommercialStatus.CANCELLED,
    },
    CommercialStatus.DEPOSIT_RECEIVED: {
        CommercialStatus.CONFIRMED,
        CommercialStatus.CANCELLED,
    },
    CommercialStatus.CONFIRMED: {CommercialStatus.COMPLETED, CommercialStatus.CANCELLED},
    CommercialStatus.CANCELLED: set(),
    CommercialStatus.COMPLETED: set(),
}

PLANNING_TRANSITIONS: dict[PlanningStatus, set[PlanningStatus]] = {
    PlanningStatus.NOT_PLANNED: {PlanningStatus.PROVISIONAL_PLAN},
    PlanningStatus.PROVISIONAL_PLAN: {
        PlanningStatus.FEASIBLE,
        PlanningStatus.AT_RISK,
        PlanningStatus.CONFLICT,
    },
    PlanningStatus.FEASIBLE: {
        PlanningStatus.AT_RISK,
        PlanningStatus.CONFLICT,
        PlanningStatus.PLANNER_APPROVED,
    },
    PlanningStatus.AT_RISK: {
        PlanningStatus.FEASIBLE,
        PlanningStatus.CONFLICT,
        PlanningStatus.PLANNER_APPROVED,
    },
    PlanningStatus.CONFLICT: {PlanningStatus.AT_RISK, PlanningStatus.FEASIBLE},
    PlanningStatus.PLANNER_APPROVED: {
        PlanningStatus.AT_RISK,
        PlanningStatus.CONFLICT,
        PlanningStatus.OPERATIONALLY_LOCKED,
    },
    PlanningStatus.OPERATIONALLY_LOCKED: {PlanningStatus.CONFLICT},
}


class JobService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_jobs(self) -> list[Job]:
        return list(self.session.scalars(select(Job).order_by(Job.site_access_at, Job.name)).all())

    def get_job(self, job_id: int) -> Job:
        job = self.session.get(Job, job_id)
        if job is None:
            raise JobNotFoundError("Job not found")
        return job

    def create_job(self, payload: dict[str, Any]) -> Job:
        values = JobData.model_validate(payload).model_dump()
        job = Job(**values)
        self.session.add(job)
        try:
            self.session.flush()
            self.generate_phases(job)
            self.session.commit()
            self.session.refresh(job)
        except IntegrityError as error:
            self.session.rollback()
            raise JobConflictError(
                "Job code must be unique and references must be valid"
            ) from error
        return job

    def update_job(self, job_id: int, payload: dict[str, Any]) -> Job:
        job = self.get_job(job_id)
        values = JobData.model_validate(payload).model_dump()
        self._validate_status_transition(job, values)
        for name, value in values.items():
            setattr(job, name, value)
        try:
            self.session.flush()
            self.generate_phases(job)
            self.regenerate_requirements(job)
            self.session.commit()
            self.session.refresh(job)
        except IntegrityError as error:
            self.session.rollback()
            raise JobConflictError("Job update conflicts with existing data") from error
        return job

    def add_tent_requirement(self, job_id: int, payload: dict[str, Any]) -> JobTentRequirement:
        job = self.get_job(job_id)
        values = JobTentRequirementData.model_validate(payload).model_dump()
        requirement = JobTentRequirement(**values)
        job.tent_requirements.append(requirement)
        self.session.flush()
        self.regenerate_requirements(job)
        self.generate_phases(job)
        self.session.commit()
        self.session.refresh(requirement)
        return requirement

    def delete_tent_requirement(self, job_id: int, requirement_id: int) -> None:
        job = self.get_job(job_id)
        requirement = self.session.get(JobTentRequirement, requirement_id)
        if requirement is None or requirement.job_id != job.id:
            raise JobNotFoundError("Tent requirement not found")
        job.tent_requirements.remove(requirement)
        self.session.flush()
        self.regenerate_requirements(job)
        self.generate_phases(job)
        self.session.commit()

    def update_phase(self, job_id: int, phase_id: int, payload: dict[str, Any]) -> JobPhase:
        self.get_job(job_id)
        phase = self.session.get(JobPhase, phase_id)
        if phase is None or phase.job_id != job_id:
            raise JobNotFoundError("Job phase not found")
        values = JobPhaseData.model_validate(payload).model_dump()
        for name, value in values.items():
            setattr(phase, name, value)
        self.session.commit()
        self.session.refresh(phase)
        return phase

    def regenerate_requirements(self, job: Job) -> list[JobEquipmentRequirement]:
        totals: dict[tuple[int, BuildStage], int] = {}
        for tent_requirement in job.tent_requirements:
            configuration = self.session.get(
                TentConfiguration, tent_requirement.tent_configuration_id
            )
            if configuration is None:
                continue
            for component in configuration.requirements:
                key = (component.equipment_type_id, component.required_stage)
                totals[key] = totals.get(key, 0) + component.quantity * tent_requirement.quantity

        generated = {
            (requirement.equipment_type_id, requirement.required_stage): requirement
            for requirement in job.equipment_requirements
            if requirement.source == RequirementSource.GENERATED
        }
        for key, generated_requirement in list(generated.items()):
            if key not in totals:
                self.session.delete(generated_requirement)

        results: list[JobEquipmentRequirement] = []
        for (equipment_type_id, stage), quantity in totals.items():
            current_requirement = generated.get((equipment_type_id, stage))
            if current_requirement is None:
                current_requirement = JobEquipmentRequirement(
                    equipment_type_id=equipment_type_id,
                    required_stage=stage,
                    source=RequirementSource.GENERATED,
                )
                job.equipment_requirements.append(current_requirement)
            current_requirement.quantity_required = quantity
            current_requirement.required_on_site_at = job.site_access_at
            current_requirement.releasable_at = job.strike_available_at
            current_requirement.status = RequirementStatus.UNRESOLVED
            results.append(current_requirement)
        self.session.flush()
        return results

    def generate_phases(self, job: Job) -> list[JobPhase]:
        generated = {
            phase.phase_type: phase
            for phase in job.phases
            if phase.source == RecordSource.GENERATED and not phase.locked
        }
        desired: dict[PhaseType, tuple[Any, Any, int]] = {
            PhaseType.BUILD: (job.site_access_at, job.must_be_up_at, self._preferred_crew(job)),
        }
        if job.show_start_at and job.show_end_at:
            desired[PhaseType.SHOW] = (job.show_start_at, job.show_end_at, 0)
            if job.maintenance_cover_required:
                desired[PhaseType.MAINTENANCE] = (job.show_start_at, job.show_end_at, 1)
        strike_end = job.site_clear_by or (
            job.strike_available_at + timedelta(hours=float(self._strike_hours(job)))
        )
        desired[PhaseType.STRIKE] = (
            job.strike_available_at,
            strike_end,
            self._preferred_crew(job),
        )
        for phase_type, generated_phase in list(generated.items()):
            if phase_type not in desired:
                self.session.delete(generated_phase)
        result: list[JobPhase] = []
        for phase_type, (start_at, end_at, headcount) in desired.items():
            current_phase = generated.get(phase_type)
            if current_phase is None:
                current_phase = JobPhase(
                    phase_type=phase_type,
                    source=RecordSource.GENERATED,
                )
                job.phases.append(current_phase)
            current_phase.start_at = start_at
            current_phase.end_at = end_at
            current_phase.required_headcount = headcount
            result.append(current_phase)
        self.session.flush()
        return result

    def _preferred_crew(self, job: Job) -> int:
        values = [
            requirement.required_crew_override
            if requirement.required_crew_override is not None
            else requirement.tent_configuration.preferred_crew
            for requirement in job.tent_requirements
        ]
        return max(values, default=0)

    def _strike_hours(self, job: Job) -> Decimal:
        values = [
            requirement.strike_duration_override_hours
            if requirement.strike_duration_override_hours is not None
            else requirement.tent_configuration.default_strike_hours
            for requirement in job.tent_requirements
        ]
        return max(values, default=Decimal("1")) or Decimal("1")

    @staticmethod
    def _validate_status_transition(job: Job, values: dict[str, Any]) -> None:
        new_commercial = values["commercial_status"]
        if (
            new_commercial != job.commercial_status
            and new_commercial not in COMMERCIAL_TRANSITIONS[job.commercial_status]
        ):
            raise JobConflictError(
                "Cannot change commercial status from "
                f"{job.commercial_status.value} to {new_commercial.value}"
            )
        new_planning = values["planning_status"]
        if (
            new_planning != job.planning_status
            and new_planning not in PLANNING_TRANSITIONS[job.planning_status]
        ):
            raise JobConflictError(
                "Cannot change planning status from "
                f"{job.planning_status.value} to {new_planning.value}"
            )
