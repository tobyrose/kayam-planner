from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.administration import BuildStage, EquipmentType
from app.models.jobs import (
    CommercialStatus,
    Job,
    JobEquipmentRequirement,
    JobPhase,
    JobTentRequirement,
    JobTentSection,
    LocalCrewBooking,
    PhaseType,
    PlanningStatus,
    RecordSource,
    RequirementSource,
    RequirementStatus,
)
from app.schemas.jobs import JobData, JobPhaseData, JobTentRequirementData, LocalCrewBookingData

BUILD_LEAD_DAYS = 5
BREAK_TRAIL_DAYS = 3


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
            self.session.commit()
            self.session.refresh(job)
        except IntegrityError as error:
            self.session.rollback()
            raise JobConflictError("Job update conflicts with existing data") from error
        return job

    def add_tent_requirement(self, job_id: int, payload: dict[str, Any]) -> JobTentRequirement:
        job = self.get_job(job_id)
        values = JobTentRequirementData.model_validate(payload).model_dump()
        codes = [token.strip() for token in values.pop("sequence").split("-") if token.strip()]
        if not codes:
            raise JobError("Enter at least one section code, e.g. K-M-M-M-K")
        equipment_types = {
            equipment_type.code: equipment_type
            for equipment_type in self.session.scalars(
                select(EquipmentType).where(EquipmentType.code.in_(codes))
            )
        }
        unknown = [code for code in codes if code not in equipment_types]
        if unknown:
            raise JobError(f"Unknown section code(s): {', '.join(unknown)}")
        non_section = [code for code in codes if equipment_types[code].category != "section"]
        if non_section:
            raise JobError(
                f"Not a bookable section type: {', '.join(non_section)} "
                "(poles and linked equipment are derived automatically)"
            )
        families = {equipment_types[code].tent_family_id for code in codes}
        if len(families) > 1:
            raise JobError("All sections in one tent must belong to the same tent family")

        other_tents = list(job.tent_requirements)
        requirement = JobTentRequirement(**values)
        job.tent_requirements.append(requirement)
        for index, code in enumerate(codes):
            requirement.sections.append(
                JobTentSection(sequence_index=index, equipment_type_id=equipment_types[code].id)
            )
        self.session.flush()
        self.regenerate_requirements(job)
        self._seed_phases_for_new_tent(job, requirement, other_tents)
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
        self.session.commit()

    def add_phase(self, job_id: int, payload: dict[str, Any]) -> JobPhase:
        """Add a phase beyond the auto-seeded set — e.g. a second Up phase to split a tent's
        contract window between two Tentmasters mid-contract (overlap allowed for handover)."""
        job = self.get_job(job_id)
        values = JobPhaseData.model_validate(payload).model_dump()
        self._validate_up_within_contract(values)
        phase = JobPhase(job_id=job.id, source=RecordSource.MANUAL, **values)
        self.session.add(phase)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise JobConflictError("Phase conflicts with existing data") from error
        self.session.refresh(phase)
        return phase

    def delete_phase(self, job_id: int, phase_id: int) -> None:
        self.get_job(job_id)
        phase = self.session.get(JobPhase, phase_id)
        if phase is None or phase.job_id != job_id:
            raise JobNotFoundError("Job phase not found")
        if phase.locked:
            raise JobConflictError("Phase is locked and cannot be removed")
        self.session.delete(phase)
        self.session.commit()

    def add_local_crew_booking(self, job_id: int, payload: dict[str, Any]) -> LocalCrewBooking:
        """Book anonymous local/hired headcount onto the job between two dates — joins whichever
        phase(s) are active over that window (see `roster.phase_roster`), not a specific phase."""
        job = self.get_job(job_id)
        values = LocalCrewBookingData.model_validate(payload).model_dump()
        booking = LocalCrewBooking(job_id=job.id, **values)
        self.session.add(booking)
        self.session.commit()
        self.session.refresh(booking)
        return booking

    def delete_local_crew_booking(self, job_id: int, booking_id: int) -> None:
        self.get_job(job_id)
        booking = self.session.get(LocalCrewBooking, booking_id)
        if booking is None or booking.job_id != job_id:
            raise JobNotFoundError("Local crew booking not found")
        self.session.delete(booking)
        self.session.commit()

    def add_ancillary_equipment(
        self, job_id: int, equipment_type_id: int, quantity: int
    ) -> JobEquipmentRequirement:
        """Manually book a non-section tracked item onto the job (stake basher, crew tent, ...)
        with no stage picker — a sensible default stage is chosen internally. Booking the same
        type again tops up the existing manual line rather than creating a duplicate."""
        job = self.get_job(job_id)
        if quantity <= 0:
            raise JobError("Quantity must be positive")
        window_start, window_end = self._requirement_window(job)
        existing = next(
            (
                requirement
                for requirement in job.equipment_requirements
                if requirement.equipment_type_id == equipment_type_id
                and requirement.source == RequirementSource.MANUAL
                and requirement.required_stage == BuildStage.COMPLETION_AND_ANCILLARY
            ),
            None,
        )
        if existing is not None:
            existing.quantity_required += quantity
            self.session.commit()
            self.session.refresh(existing)
            return existing
        requirement = JobEquipmentRequirement(
            job_id=job.id,
            equipment_type_id=equipment_type_id,
            quantity_required=quantity,
            required_on_site_at=window_start,
            releasable_at=window_end,
            required_stage=BuildStage.COMPLETION_AND_ANCILLARY,
            source=RequirementSource.MANUAL,
        )
        self.session.add(requirement)
        self.session.commit()
        self.session.refresh(requirement)
        return requirement

    def update_phase(self, job_id: int, phase_id: int, payload: dict[str, Any]) -> JobPhase:
        phase = self._apply_phase_update(job_id, phase_id, payload)
        self.session.commit()
        self.session.refresh(phase)
        return phase

    def update_phases(
        self, job_id: int, updates: list[tuple[int, dict[str, Any]]]
    ) -> list[JobPhase]:
        """Apply several phase edits in one transaction (job-edit "Save all phases")."""
        self.get_job(job_id)
        results: list[JobPhase] = []
        for phase_id, payload in updates:
            results.append(self._apply_phase_update(job_id, phase_id, payload))
        self.session.commit()
        for phase in results:
            self.session.refresh(phase)
        return results

    def _apply_phase_update(
        self, job_id: int, phase_id: int, payload: dict[str, Any]
    ) -> JobPhase:
        self.get_job(job_id)
        phase = self.session.get(JobPhase, phase_id)
        if phase is None or phase.job_id != job_id:
            raise JobNotFoundError("Job phase not found")
        values = JobPhaseData.model_validate(payload).model_dump()
        self._validate_up_within_contract(values)
        for name, value in values.items():
            setattr(phase, name, value)
        return phase

    def _validate_up_within_contract(self, values: dict[str, Any]) -> None:
        """An Up phase can be freely split across Tentmasters (a handover overlap day is fine),
        but must never extend outside its tent's fixed contract window."""
        if values["phase_type"] != PhaseType.UP:
            return
        tent = self.session.get(JobTentRequirement, values["job_tent_requirement_id"])
        if tent is None:
            raise JobError("Tent requirement not found")
        if values["start_at"] < tent.contracted_up_at or values["end_at"] > tent.contracted_down_at:
            from app.time_display import wall_clock_display

            raise JobError(
                "Up phase must stay within the tent's contract window "
                f"({wall_clock_display(tent.contracted_up_at)} – "
                f"{wall_clock_display(tent.contracted_down_at)})"
            )

    def reassign_phase_tentmaster(self, phase_id: int, tentmaster_id: int | None) -> JobPhase:
        """Move a phase to a different Tentmaster (or unassign it) without touching anything
        else — used by the season board's drag-and-drop, as distinct from `update_phase()`'s
        full-form edit. Double-booking is reported on the conflicts page, not blocked here,
        matching the rest of the app's "planner controls, system flags" approach (D013).

        When the dragged phase is an Up phase, every other unlocked Up phase on the same job
        that currently shares the same Tentmaster (including both unassigned) moves with it —
        so multi-tent jobs stay as one board block after a drag.
        """
        phase = self.session.get(JobPhase, phase_id)
        if phase is None:
            raise JobNotFoundError("Job phase not found")
        if phase.locked:
            raise JobConflictError("Phase is locked and cannot be reassigned")
        siblings: list[JobPhase] = [phase]
        if phase.phase_type == PhaseType.UP:
            siblings = list(
                self.session.scalars(
                    select(JobPhase).where(
                        JobPhase.job_id == phase.job_id,
                        JobPhase.phase_type == PhaseType.UP,
                        JobPhase.tentmaster_id == phase.tentmaster_id,
                    )
                )
            )
        for item in siblings:
            if item.locked:
                if item.id == phase.id:
                    raise JobConflictError("Phase is locked and cannot be reassigned")
                continue
            item.tentmaster_id = tentmaster_id
        self.session.commit()
        self.session.refresh(phase)
        return phase

    def regenerate_requirements(self, job: Job) -> list[JobEquipmentRequirement]:
        totals: dict[tuple[int, BuildStage], int] = {}
        for tent_requirement in job.tent_requirements:
            self._expand_tent_requirement(tent_requirement, totals)

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
            window_start, window_end = self._requirement_window(job)
            current_requirement.quantity_required = quantity
            current_requirement.required_on_site_at = window_start
            current_requirement.releasable_at = window_end
            current_requirement.status = RequirementStatus.UNRESOLVED
            results.append(current_requirement)
        self.session.flush()
        return results

    def _requirement_window(self, job: Job) -> tuple[datetime, datetime]:
        """The outer bound equipment must be on site for: from the earliest tent's Build start to
        the latest tent's Break end, across every tent on the job."""
        if not job.tent_requirements:
            raise JobError("Add a tent requirement first")
        starts = [
            requirement.contracted_up_at - timedelta(days=BUILD_LEAD_DAYS)
            for requirement in job.tent_requirements
        ]
        ends = [
            requirement.contracted_down_at + timedelta(days=BREAK_TRAIL_DAYS)
            for requirement in job.tent_requirements
        ]
        return min(starts), max(ends)

    def _expand_tent_requirement(
        self, tent_requirement: JobTentRequirement, totals: dict[tuple[int, BuildStage], int]
    ) -> None:
        """Add one tent requirement's sections, derived poles, and cascaded linked equipment
        into `totals`. Sections contribute one unit each per booked tent; poles are computed from
        the section count via the sequence's `TentFamily` formula; each of those, in turn,
        cascades through any `EquipmentLink` rows (recursively, cycle-guarded).
        """

        sections = tent_requirement.sections
        if not sections:
            return
        quantity = tent_requirement.quantity
        for section in sections:
            equipment_type = section.equipment_type
            self._add_equipment(equipment_type, quantity, totals)
            self._expand_links(equipment_type, quantity, totals, visited={equipment_type.id})

        family = tent_requirement.tent_family
        if family is None or family.pole_equipment_type_id is None:
            return
        pole_type = family.pole_equipment_type
        assert pole_type is not None
        total_poles = max(
            0, len(sections) * family.pole_count_multiplier + family.pole_count_offset
        )
        pole_asset_quantity = -(-total_poles // pole_type.pack_size)  # ceil division
        if pole_asset_quantity <= 0:
            return
        pole_quantity = pole_asset_quantity * quantity
        self._add_equipment(pole_type, pole_quantity, totals)
        self._expand_links(pole_type, pole_quantity, totals, visited={pole_type.id})

    def _expand_links(
        self,
        equipment_type: EquipmentType,
        parent_quantity: int,
        totals: dict[tuple[int, BuildStage], int],
        *,
        visited: set[int],
    ) -> None:
        for link in equipment_type.outgoing_links:
            if link.child_equipment_type_id in visited:
                continue  # defensive cycle guard; EquipmentLink also rejects direct self-links
            child_type = link.child_equipment_type
            child_quantity = parent_quantity * link.quantity_per_parent
            self._add_equipment(child_type, child_quantity, totals)
            self._expand_links(
                child_type, child_quantity, totals, visited=visited | {child_type.id}
            )

    @staticmethod
    def _add_equipment(
        equipment_type: EquipmentType,
        quantity: int,
        totals: dict[tuple[int, BuildStage], int],
    ) -> None:
        key = (equipment_type.id, equipment_type.default_build_stage)
        totals[key] = totals.get(key, 0) + quantity

    def _seed_phases_for_new_tent(
        self,
        job: Job,
        requirement: JobTentRequirement,
        other_tents: list[JobTentRequirement],
    ) -> None:
        """Seed a starting set of phases when a tent is added — a one-time seed, not a
        continuously re-synced desired state (the planner freely edits/adds/removes phases
        afterward via `add_phase()`/`update_phase()`/`delete_phase()`).

        Always seeds this tent's own Up phase. If it's the job's first tent, also seeds the
        job-level Build (contract Up minus `BUILD_LEAD_DAYS`) and Break (contract Down plus
        `BREAK_TRAIL_DAYS`) — the same crew typically builds/strikes every tent together. If a
        later tent's Up is after an already-seeded tent's Up, an extra Build segment is seeded
        between the two, since that gap is genuinely more build work, not idle time.
        """
        preferred_crew = requirement.tent_family.preferred_crew if requirement.tent_family else 0
        job.phases.append(
            JobPhase(
                phase_type=PhaseType.UP,
                job_tent_requirement_id=requirement.id,
                start_at=requirement.contracted_up_at,
                end_at=requirement.contracted_down_at,
                required_headcount=preferred_crew,
                source=RecordSource.GENERATED,
            )
        )
        if not other_tents:
            job.phases.append(
                JobPhase(
                    phase_type=PhaseType.BUILD,
                    start_at=requirement.contracted_up_at - timedelta(days=BUILD_LEAD_DAYS),
                    end_at=requirement.contracted_up_at,
                    required_headcount=preferred_crew,
                    source=RecordSource.GENERATED,
                )
            )
            job.phases.append(
                JobPhase(
                    phase_type=PhaseType.BREAK,
                    start_at=requirement.contracted_down_at,
                    end_at=requirement.contracted_down_at + timedelta(days=BREAK_TRAIL_DAYS),
                    required_headcount=preferred_crew,
                    source=RecordSource.GENERATED,
                )
            )
        else:
            earliest_up = min(tent.contracted_up_at for tent in other_tents)
            if requirement.contracted_up_at > earliest_up:
                job.phases.append(
                    JobPhase(
                        phase_type=PhaseType.BUILD,
                        start_at=earliest_up,
                        end_at=requirement.contracted_up_at,
                        required_headcount=preferred_crew,
                        source=RecordSource.GENERATED,
                    )
                )
        self.session.flush()

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
