# IMPLEMENTATION_PLAN.md

# Kayam Seasonal Planning System — V1 Implementation Plan

This plan breaks V1 into controlled milestones. Keep the application runnable after each milestone.

Use these statuses:

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete
- `[!]` Blocked

Do not mark a milestone complete until its acceptance criteria pass.

---

# Milestone 0 — Repository preparation

## Tasks

- [x] Add `SPECIFICATION.md`.
- [x] Add `AGENTS.md`.
- [x] Add `DECISIONS.md`.
- [x] Add `OPEN_QUESTIONS.md`.
- [x] Add this file.
- [x] Create `reference/`.
- [x] Copy `DAILY V8.xlsx` into `reference/`.
- [x] Create `.gitignore`.
- [x] Initialise Git if required.

## Acceptance criteria

- All planning documents exist at repository root.
- The reference workbook is retained but not committed if business policy forbids it.
- Codex can identify the product purpose without external chat context.

---

# Milestone 1 — Application foundation

## Deliverables

- FastAPI application
- SQLAlchemy setup
- Alembic
- SQLite configuration
- Jinja base layout
- Static asset structure
- Health endpoint
- Test setup
- Development seed command
- Initial README

## Tasks

- [x] Create `pyproject.toml`.
- [x] Configure Python 3.12+.
- [x] Add FastAPI, Uvicorn, SQLAlchemy, Alembic, Jinja2, HTMX support and pytest.
- [x] Add Ruff.
- [x] Add optional mypy configuration.
- [x] Create application package layout.
- [x] Add `app/config.py` using Pydantic settings.
- [x] Add `.env.example`.
- [x] Add database session management.
- [x] Add initial Alembic migration framework.
- [x] Add base HTML template and navigation shell.
- [x] Add `/health`.
- [x] Add a simple homepage.
- [x] Add test database fixture.
- [x] Add smoke tests.
- [x] Document installation and run commands.

## Acceptance criteria

- `python -m pytest` passes.
- `alembic upgrade head` succeeds on a clean database.
- The app starts locally.
- `/health` returns a successful response.
- README allows setup on macOS, Windows and Linux.

---

# Milestone 2 — Core administration

## Deliverables

CRUD administration for:

- Locations
- Tent families
- Equipment types
- Equipment assets
- Tent configurations
- Tentmaster teams
- Crew members
- Tentmaster memberships
- Crew availability
- Lorry types
- Lorries
- Vans
- Hauliers

## Tasks

### Location

- [x] Create Location model and migration.
- [x] Add location list/create/edit/detail pages.
- [x] Support location type.
- [x] Support timezone.
- [x] Support manual coordinates.
- [x] Seed Oxford Yard.

### Tent and equipment catalogue

- [x] Create TentFamily.
- [x] Create EquipmentType.
- [x] Create EquipmentAsset.
- [x] Add individual versus quantity tracking mode.
- [x] Create TentConfiguration.
- [x] Create TentConfigurationRequirement.
- [x] Add configuration editor for component quantities.

### Crew

- [x] Create Tentmaster.
- [x] Create CrewMember.
- [x] Create TentmasterMembership.
- [x] Create CrewAvailability.
- [x] Validate membership overlaps.

### Vehicles and suppliers

- [x] Create LorryType.
- [x] Create Lorry.
- [x] Create Van.
- [x] Create Haulier.
- [x] Support multi-dimensional lorry capacity.

### Seed data

- [x] Seed four example Tentmasters.
- [x] Seed Kayam example configurations.
- [x] Seed example equipment.
- [x] Seed example lorry type and van.

## Tests

- [x] Unique asset code.
- [x] Tentmaster membership overlap.
- [x] Configuration requirements.
- [x] Capacity field validation.
- [x] Location timezone validation.

## Acceptance criteria

- An admin can create every core reference entity.
- A 10-pole template can be configured without code changes.
- A named asset such as K1 can be created.
- Oxford Yard behaves as a normal location.

---

# Milestone 3 — Jobs, statuses and phases

## Deliverables

- Job CRUD
- Commercial and planning statuses
- Contract milestones
- Tent requirements
- Generated equipment requirements
- Generated job phases

## Tasks

- [x] Create Job model.
- [x] Create JobTentRequirement.
- [x] Create JobEquipmentRequirement.
- [x] Create JobPhase.
- [x] Add date-order validation.
- [x] Add commercial-status workflow.
- [x] Add planning-status workflow.
- [x] Build job-list page.
- [x] Build multi-section job editor.
- [x] Add tent requirements to a job.
- [x] Implement component expansion service.
- [x] Implement requirement regeneration preserving manual changes.
- [x] Generate default build and strike phases.
- [x] Allow phase overrides.
- [x] Display a generated component summary.

## Tests

- [x] Date validation.
- [x] 10-pole requirement expansion.
- [x] Multiplication for multiple tents.
- [x] Preservation of manual requirements.
- [x] Phase generation.

## Acceptance criteria

- A user can create an enquiry at a location.
- Adding a tent configuration generates correct requirements.
- Job milestones are validated.
- Build and strike phases are visible and editable.

---

# Milestone 4 — Crew planning

## Deliverables

- Crew assignments
- Required headcount
- Daily crew totals
- Crew conflicts
- Initial crew planning board
- Date-range creation

## Tasks

- [x] Create CrewAssignment.
- [x] Support named people and placeholders.
- [x] Assign Tentmaster at phase level.
- [x] Calculate required, assigned and shortfall counts.
- [x] Detect overlapping named assignments.
- [x] Respect CrewAvailability.
- [x] Calculate daily Tentmaster totals.
- [x] Calculate daily company total.
- [x] Build a date-oriented crew board.
- [x] Add date-range selection.
- [x] Open `Add Job or Activity` from selection.
- [x] Add non-job activities such as training, leave and yard work.
- [x] Show provisional versus confirmed styling.

## Tests

- [x] Named crew overlap.
- [x] Unavailability conflict.
- [x] Placeholder count.
- [x] Daily totals.
- [x] Multiple Tentmasters on one job.

## Acceptance criteria

- Crew assignments are explicit rather than hidden comments.
- The board shows Tentmaster work against dates.
- Clicking a crew count reveals names.
- Shortages and conflicts are visible.

---

# Milestone 5 — Equipment allocation

## Deliverables

- Equipment assignments
- Soft and hard allocations
- Locks
- Compatibility checks
- Asset timeline
- Equipment conflict detection

## Tasks

- [x] Create EquipmentAssignment.
- [x] Implement compatibility service.
- [x] Implement hard-overlap detection.
- [x] Implement soft-overlap warnings.
- [x] Add allocation source.
- [x] Add lock support.
- [x] Build candidate-asset query.
- [x] Order candidates by availability and location.
- [x] Build job equipment-assignment UI.
- [x] Build asset detail and timeline page.
- [x] Derive asset state over time.
- [x] Show unexplained location gaps.

## Tests

- [x] Hard overlap.
- [x] Soft competition.
- [x] Compatibility rejection.
- [x] Locked assignment preservation.
- [x] Asset-state derivation.

## Acceptance criteria

- A planner can assign K1 to a job.
- Confirmed overlapping hard allocation is prevented or reported.
- Provisional competition is visible.
- Clicking an asset shows its expected seasonal journey.

---

# Milestone 6 — Equipment movements and loads

## Deliverables

- Equipment movements
- Numbered loads
- Load contents
- Lorry capacity
- Load lifecycle
- Oxford staging
- Loads export

## Tasks

- [x] Create EquipmentMovement.
- [x] Create Load.
- [x] Create LoadItem.
- [x] Generate movement requirements from equipment transitions.
- [x] Support one movement with multiple loads.
- [x] Add load-number validation.
- [x] Add load lifecycle.
- [x] Add individual and quantity load items.
- [x] Calculate capacity in all dimensions.
- [x] Show near-capacity and over-capacity warnings.
- [x] Allow movement through Oxford Yard.
- [x] Validate location continuity.
- [x] Build loads list.
- [x] Build load detail.
- [x] Add CSV export.
- [x] Add printable load sheet.

## Tests

- [x] Capacity within limit.
- [x] Over-capacity load.
- [x] Multi-load movement.
- [x] Asset location continuity.
- [x] Locked-load behaviour.

## Acceptance criteria

- A numbered load can be created and sent between locations.
- Contents are visible and capacity is calculated.
- An asset can move through Oxford before its next job.
- Loads list can be exported.

---

# Milestone 7 — Routing and travel feasibility

## Deliverables

- Routing provider abstraction
- OpenRouteService adapter
- Manual fallback
- Geocoding
- Route cache
- Travel feasibility
- Timing-margin warnings

## Tasks

- [x] Define routing domain objects.
- [x] Define provider protocol.
- [x] Add OpenRouteService adapter.
- [x] Add manual provider.
- [x] Add location geocoding workflow.
- [x] Add geocoding confirmation.
- [x] Create RouteCache.
- [x] Cache by origin, destination and vehicle profile.
- [x] Store pure driving duration.
- [x] Store operational allowances.
- [x] Calculate operational journey duration.
- [x] Implement direct asset-transition feasibility.
- [x] Add configurable green/amber/red thresholds.
- [x] Show receiving-crew warning.
- [x] Handle missing API key cleanly.

## Tests

- [x] Cache-key stability.
- [x] Manual fallback.
- [x] Feasible direct transition.
- [x] Infeasible transition.
- [x] Margin status.
- [x] Receiving-crew warning.

## Acceptance criteria

- Locations can store confirmed coordinates.
- A route can be calculated or manually entered.
- Asset transitions show time margin.
- The app remains functional without external routing.

---

# Milestone 8 — Crew movements and vans

## Deliverables

- Crew movement records
- Journey legs
- Passengers
- Vans
- Flights and ferries
- Crew-move export

## Tasks

- [x] Create CrewMovement.
- [x] Create CrewJourneyLeg.
- [x] Create CrewMovementPassenger.
- [x] Support named and placeholder passengers.
- [x] Assign van.
- [x] Validate passenger capacity.
- [x] Support flight, ferry, train and transfer legs.
- [x] Validate arrival before work.
- [x] Show Tentmaster joining/leaving changes.
- [x] Build crew-moves list.
- [x] Add CSV export.
- [x] Add printable movement detail.

## Tests

- [x] Van over capacity.
- [x] Late crew arrival.
- [x] Multi-leg journey.
- [x] Passenger assignment.
- [x] Tentmaster transfer.

## Acceptance criteria

- A crew move such as CM16 can be created.
- It may include van, ferry and flight legs.
- Passengers and capacity are validated.
- Crew moves can be exported.

---

# Milestone 9 — Costing

## Deliverables

- Crew rates
- Labour estimates
- Travel estimates
- Load estimates
- Actual load costs
- Supplier invoices
- Cost allocations
- Job margins

## Tasks

- [x] Implement crew work-cost service.
- [x] Implement crew travel-cost service.
- [x] Implement load-estimate service.
- [x] Add manual estimate override.
- [x] Add estimate source.
- [x] Create SupplierInvoice.
- [x] Create LoadCostAllocation.
- [x] Record cost categories.
- [x] Allocate one invoice across several loads.
- [x] Calculate estimate-versus-actual variance.
- [x] Calculate job estimated margin.
- [x] Calculate job actual margin where data exists.
- [x] Build cost summary pages.

## Tests

- [x] Labour estimate.
- [x] Travel estimate.
- [x] Load estimate.
- [x] Manual override.
- [x] Invoice allocation.
- [x] Margin calculation.

## Acceptance criteria

- Each load can hold estimated and actual cost.
- One invoice can be allocated across several loads.
- A job shows estimated margin.
- Actual variance is visible.

---

# Milestone 10 — Combined seasonal board

## Deliverables

- Synchronized crew and equipment board
- Shared date axis
- Compact day rows
- Sticky headers
- Search and highlighting
- Zoom and filters
- Side-panel editing

## Tasks

- [x] Define board data endpoint.
- [x] Query a selected season/date range efficiently.
- [x] Render shared date rows.
- [x] Render Tentmaster lanes.
- [x] Render equipment/location/movement lanes.
- [x] Mark Oxford Yard periods.
- [x] Display load numbers.
- [x] Display contract milestones.
- [x] Add asset highlighting.
- [x] Add job highlighting.
- [x] Add load highlighting.
- [x] Add confirmed/provisional patterns.
- [x] Add conflict indicators.
- [x] Add zoom levels.
- [x] Add filters.
- [x] Add sticky headers.
- [x] Add side-panel editing.
- [x] Ensure keyboard accessibility where practical.

## Performance checks

- [x] Test several hundred assets.
- [x] Test several hundred jobs.
- [x] Avoid one query per board cell.
- [x] Use date-range queries and aggregation.

## Acceptance criteria

- Users can understand the flow of people and equipment across a season.
- Selecting K1 highlights its complete journey.
- Selecting a job highlights crew, equipment and loads.
- Provisional and confirmed work are visually distinct.
- The board remains usable at desktop width.

---

# Milestone 11 — Conflict centre and assisted suggestions

## Deliverables

- Central conflict list
- Direct movement suggestions
- Existing-load capacity suggestions
- Manual approval workflow

## Tasks

- [x] Aggregate hard conflicts.
- [x] Aggregate conditional conflicts.
- [x] List unresolved equipment requirements.
- [x] List missing crew.
- [x] List missing transport.
- [x] List over-capacity loads.
- [x] List receiving warnings.
- [x] Suggest direct equipment movements.
- [x] Identify obvious existing loads with spare capacity.
- [x] Require explicit acceptance.
- [x] Preserve locks.

## Acceptance criteria

- Every warning links to the affected record.
- Suggestions never silently become committed plans.
- Existing spare-capacity opportunities can be reviewed.

---

# Milestone 12 — Audit, backup and hardening

## Deliverables

- Audit log
- Database backup
- JSON export
- Restore documentation
- Workbook diagnostic script
- Packaging guidance
- Performance and security review

## Tasks

- [x] Create AuditLog.
- [x] Audit important changes.
- [x] Add database backup command.
- [x] Add admin backup action.
- [x] Add core JSON export.
- [x] Document restore.
- [x] Add workbook diagnostic script.
- [x] Read values, fills, merges and comments.
- [x] Detect LD and CM notation.
- [x] Export diagnostic JSON.
- [x] Review indexes.
- [x] Review transaction boundaries.
- [x] Review HTML escaping.
- [x] Review localhost binding.
- [x] Complete integration test suite.
- [x] Document future hosted deployment.

## Acceptance criteria

- A planner can back up the application.
- Important changes are auditable.
- The workbook can be inspected diagnostically.
- The full test suite passes.
- V1 definition of complete in `SPECIFICATION.md` is satisfied.

---

# First Codex task

Ask Codex to do only this initially:

```text
Read AGENTS.md, SPECIFICATION.md, DECISIONS.md, OPEN_QUESTIONS.md and IMPLEMENTATION_PLAN.md.

Implement Milestone 1 only.

Do not begin later milestones.

Create the project foundation, tests, README, configuration, initial migration setup and local run instructions. Keep the app runnable. Record any assumptions in DECISIONS.md or OPEN_QUESTIONS.md.
```
