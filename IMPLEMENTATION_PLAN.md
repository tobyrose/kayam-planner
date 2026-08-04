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
- [~] Add date-range selection. Corrected 2026-08-02: no drag gesture exists on any board; the
  crew board only offers a start-date field and a month/quarter/season dropdown, and each day
  cell has a static "+" link, not a draggable range.
- [~] Open `Add Job or Activity` from selection. Corrected 2026-08-02: the "+" link opens an
  activity-creation form (training/leave/yard work/travel/other per spec 11.4) but does not offer
  "New job" or "Existing job phase" as options.
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
- [~] Add zoom levels. Corrected 2026-08-02: only a compact/comfortable font-size toggle exists
  (`app/static/css/app.css` `[data-zoom]` rules); the visible date range never changes, so this is
  not the year/month/week zoom spec 11.1 calls for.
- [~] Add filters. Corrected 2026-08-02: only the free-text search/highlight box in
  `app/static/js/board.js` exists; there are no separate filter controls.
- [~] Add side-panel editing. Corrected 2026-08-02: the side panel shows a summary of the clicked
  block and a link to the full record page; it does not support in-place editing.
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

# Post-V1 — Crew model rework (2026-08-02)

A review against the real reference workbooks and direct owner correction found that the V1 crew
model was fundamentally wrong: a Tentmaster is a named individual leading a crew (confirmed by
`reference/LOADS 26 V8.xlsx`'s `TM DETAILS` sheet), and crew membership should be managed once,
over time, not re-entered per job phase. See `DECISIONS.md` D029 for the full rationale.

## Tasks

- [x] Resolve Q036: half-open `TentmasterMembership` dates so same-day Tentmaster handover works.
- [x] Add `app/services/roster.py`: bounded roster derivation from `TentmasterMembership` +
  `CrewAvailability`.
- [x] Add a visual crew roster board (`/planning/roster`) to manage Tentmaster membership over
  time, with a transactional move action.
- [x] Repurpose `CrewAssignment` to placeholders plus explicit ADD/EXCLUDE overrides; drop the
  dead `tentmaster_id` tag.
- [x] Rewrite `CrewPlanningService`, `CostingService.crew_work_cost()`, `BoardService`, and
  `ConflictCentreService` to consume the derived roster.
- [x] Fix two latent conflict-centre bugs (crew shortfall and receiving-crew checks reading
  `phase.crew_assignments` directly, which is empty for the common fully-staffed case).
- [x] Fix the crew board's daily total being global instead of per-Tentmaster.
- [x] Correct two false-complete checkboxes found during this review (Milestone 4 drag-to-create,
  Milestone 10 zoom/filters/side-panel editing) above.
- [x] Update seed data to demonstrate the new model (derived roster plus one ADD and one EXCLUDE
  override).

## Acceptance criteria

- A planner can assign a Tentmaster to a job phase and see headcount/names appear automatically
  from that Tentmaster's current roster, with no per-person data entry.
- Moving a crew member between Tentmasters on the roster board immediately updates every affected
  job phase.
- `python -m pytest`, `python -m ruff check .`, `python -m mypy app`, and
  `python -m alembic upgrade head` / `alembic check` all pass.

---

# Post-V1 — Tent/equipment BOM rework (2026-08-02)

The V1 tent model was also fundamentally wrong: it represented a tent as a named,
pole-count-sized template (e.g. "Kayam 10-pole") with a flat bill of materials, but the business
books tents as a sequence of section codes (e.g. K-M-M-M-K) — many different combinations produce
the same pole count, so a size-named template can never faithfully represent what was actually
booked. See `DECISIONS.md` D030 for the full rationale.

## Tasks

- [x] Rebuild `EquipmentType.code` around the real letter-code taxonomy (K, M, m, S, T, SC, V,
  VOE, VNE, P, X, AD, SB, VB, RD, CT) instead of generic category names.
- [x] Add `EquipmentType.pack_size` (physical units per tracked asset, e.g. 2 for a pole pair).
- [x] Add `EquipmentLink` (self-referential BOM: parent equipment type → child + quantity),
  admin-editable, cycle-guarded both at write time and defensively at expansion time.
- [x] Add `JobTentSection` (ordered section-code sequence per `JobTentRequirement`), replacing
  `TentConfiguration`.
- [x] Add `TentFamily.pole_count_multiplier`/`pole_count_offset`/`pole_equipment_type_id` so poles
  are derived from the sequence length via a configurable formula, not entered directly.
- [x] Remove `TentConfiguration`/`TentConfigurationRequirement` entirely (not kept alongside).
- [x] Rewrite `JobService.regenerate_requirements()` as a recursive expansion engine, preserving
  the existing GENERATED/MANUAL distinction exactly.
- [x] Replace the tent-configuration dropdown with hyphen-delimited section-sequence entry on the
  job form; split the generated summary into a visible loading list (sections + derived poles) and
  a collapsed linked-equipment detail view.
- [x] Update admin catalog: remove tent-configuration screens, add `equipment-links`, extend
  `tent-families` and `equipment-types` forms for the new fields.
- [x] Migrate existing data in place: re-point existing `EquipmentAsset` rows at their renamed
  types (no FK remapping needed) and reconstruct existing jobs' section sequences from their old
  named configuration's BOM before dropping the old tables.
- [x] Seed only the two link ratios the owner actually confirmed (M → 2 bale rings; P → 2 side
  guys + 2× 1.5t Tifors); log every other gap in `OPEN_QUESTIONS.md` (Q038-Q041) rather than guess.

## Acceptance criteria

- A planner can enter a section sequence like `K-M-M-M-K` on a job and see K/M counts, derived
  pole count, and cascaded linked equipment all appear automatically.
- Existing seeded jobs' tent requirements survive the migration with correct section sequences and
  matching derived quantities.
- `python -m pytest`, `python -m ruff check .`, `python -m mypy app`, and
  `python -m alembic upgrade head` / `alembic check` all pass, including against a copy of the
  real dev database (not just a fresh one).

---

# Post-V1 — Season board redesign (2026-08-02)

The V1 combined board (`/planning`) rendered every multi-day job phase as an identical block
repeated on every day it spanned, mixed job milestones/duplicate phase blocks/equipment movements
into one "Jobs & equipment" column, and had no way to place an unconfirmed or not-yet-crewed job
on the board without assigning it to a Tentmaster first. See `DECISIONS.md` D031 for the full
rationale.

## Tasks

- [x] Add `BoardBlock.segment` (`solo`/`start`/`mid`/`end`) computed from each record's own
  start/end dates (not clipped to the requested board range), and CSS to merge same-record blocks
  across consecutive day-rows into one continuous bar per Tentmaster column.
- [x] Add an "Unassigned / quoted" lane for job phases with no `tentmaster_id`, positioned like an
  extra Tentmaster column, so unconfirmed jobs can be seen in context before being assigned a crew.
- [x] Split the old mixed "Jobs & equipment" column into single-purpose "Milestones" (job MUST BE
  UP / STRIKE dates) and "Equipment" (asset movements) columns; stop duplicating phase blocks into
  either, since they now render exactly once (Tentmaster column or unassigned lane).
- [x] `BoardDay.operations` → `unassigned` / `milestones` / `equipment`; `BoardService.build()`,
  the combined board template, and `app.css` (td/th padding split, `seg-*` merge rules) updated
  together; no schema or migration change (presentation-layer only).

## Acceptance criteria

- A multi-day job phase or crew activity renders as one visually continuous bar in its
  Tentmaster's column, not the same label repeated on every day.
- A job phase with no Tentmaster assigned appears in the "Unassigned / quoted" lane and nowhere
  else (not duplicated into Milestones or Equipment).
- `python -m pytest`, `python -m ruff check .`, and `python -m mypy app` all pass; verified against
  the real seeded dev database via a live server + curl (an unassigned demo phase and several
  multi-day phases were confirmed to render with the correct lane/segment).

---

# Post-V1 — Loads/equipment flow diagram (2026-08-02, revised same day)

The owner asked for a visual "loads / equipment flow diagram like the sheet." First shipped as a
horizontal space-time (Marey) chart — locations as lanes, time left-to-right — then rebuilt the
same day after feedback that it needed to actually match the sheet's own shape: dates down the
side, location/job blocks as columns, load lines connecting them on the correct date. See
`DECISIONS.md` D032 for the full history and rationale of both versions.

## Tasks (current version)

- [x] `app/services/flow.py`: `FlowService.build()` — bounded, eager-loaded queries over both
  `Job` (for site-occupancy blocks) and `EquipmentMovement`/`Load`/`LoadItem` (for transit lines)
  over a date range; assigns one column per involved `Location` (yard/depot first, then sites
  alphabetically) and computes every pixel coordinate (cell blocks, edge lines) server-side.
- [x] New route `GET /planning/flow`, reusing the season board's `_range()` default-window helper.
- [x] Rebuilt template `app/templates/planning/flow_diagram.html` — a season-board-shaped table
  (`table-layout: fixed`, sticky date column, fixed row heights) with one column per location,
  reusing `.season-block`/segment-merge CSS for job-occupancy blocks, plus an absolutely-positioned
  SVG overlay drawing one line per load movement between its origin and destination columns.
- [x] Flow page reuses the season board's toolbar (filter/zoom) and `board.js` unmodified for its
  block cells; `app/static/js/flow.js` handles clicks on the SVG line edges, sharing the same
  `#board-panel` side panel.
- [x] Nav link ("Flow diagram") added to `base.html` next to "Season board".
- [x] `tests/test_flow.py`: job-cell assembly (tent sequence, segment continuity), edge assembly,
  empty-range handling, a multi-load edge summary, and a bounded-query-count guard.

## Acceptance criteria

- `/planning/flow` renders a column per active location, with a job's booked tent sequence shown
  as a contiguous block for every day it occupies that site, and a line connecting the correct two
  columns at the correct depart/arrival date rows, for the seeded demo data and a real copy of
  `instance/kayam.db`.
- A direct site-to-site move (no yard stop) renders as a single line touching neither column it
  doesn't actually visit.
- `python -m pytest`, `python -m ruff check .`, and `python -m mypy app` all pass.

---

# Post-V1 — Season board and roster refinements (2026-08-02)

Follow-up feedback after using the season board and roster board built under the "Season board
redesign" phase above. See `DECISIONS.md` D033 for full rationale.

## Tasks

- [x] Season board job/activity blocks in Tentmaster/unassigned columns now stretch to fill the
  full row height (`.lane-cell` flex layout), instead of leaving whitespace when another column in
  the same row is taller.
- [x] Job block subtitles now include the job's tent section sequence and, on the phase's actual
  start/end day, an `UP hh:mm` / `DN hh:mm` marker — matching the reference sheet's inline
  up/down-time convention.
- [x] Drag-and-drop job reassignment: dragging a job block onto a different Tentmaster's column (or
  Unassigned) reassigns `JobPhase.tentmaster_id` via new `JobService.reassign_phase_tentmaster()`
  and route `POST /planning/move-phase`, mirroring the roster board's existing crew drag-and-drop.
- [x] Roster board: each Tentmaster's column tints amber and shows the job code on dates they're
  booked on a job (`RosterBoardService` now also queries `JobPhase`), so crew moves can be planned
  with the season's shape visible.
- [x] Tests: `test_reassign_phase_tentmaster_*` (service), `test_move_phase_route_*` (route),
  `test_job_block_shows_tent_sequence_and_boundary_times`, `test_roster_board_shows_job_label_*`.

## Acceptance criteria

- A single-day job block visually fills its day cell; a multi-day block reads as one continuous
  bar with no internal gap (already true from the prior phase, unaffected by the fill fix).
- Dragging a job block to a different Tentmaster column persists immediately and is reflected on
  reload; a locked phase rejects the move with a visible error.
- `python -m pytest`, `python -m ruff check .`, and `python -m mypy app` all pass.

---

# Post-V1 roadmap

Agreed with the product owner 2026-08-02, after a review found several fundamentals in the
original V1 build didn't match how the business actually works (see D029, D030). Update the
status marker as each phase starts/lands; each phase gets its own `# Post-V1 — <name>` section
above (or below, as they land) with full task/acceptance detail once it's underway.

| # | Phase | Status |
| --- | --- | --- |
| 1 | Crew model rework — Tentmaster-derived rosters, roster board, drag-and-drop, availability windows, configurable role/employment type | Done |
| 2 | Tent/equipment BOM rework — section-sequence tents, derived poles, linked-equipment cascade | Done |
| 3 | Season board redesign — contiguous Tentmaster blocks (not per-day flags), an unassigned/quoted lane, drop the confusing "Jobs & equipment" column | Done |
| 4 | Loads/equipment flow diagram — a visual flow diagram of equipment movement, like the reference sheet | Done |
| 5 | Automatic load-design/routing engine with manual override — V1 cut shipped 2026-08-04 (`SeasonPlanService`, button on `/loads`). Design + remaining gaps in `LOAD_ENGINE_DESIGN.md` §5. Loads Diagram UI still not built. | V1 done; diagram / refinements open |
| 6 | Operational model redesign round — real-usage feedback on phases 3 & 4 above (see chunk list below) | Done |

---

# Post-V1 — Operational model redesign round (2026-08-03)

After using the board/roster/flow pages from phases 3 & 4, the owner gave a large batch of
real-usage feedback (list preserved in the 2026-08-03 conversation) requiring a genuine rework of
the operational-phase model, not just presentation fixes. Sequenced in chunks, each landed and
checked against the running app before the next starts (see `DECISIONS.md` D034 onward for
per-chunk detail).

## Chunks

- [x] **1. Crew availability → crew member's own page.** D034. Done.
- [x] **2. Roster drag-and-drop cascade fix + grey-out unavailable.** D035. Done.
- [x] **3. Operational phases rework.** D036. Done — migration `e71a563ebf28` applied to
  `instance/kayam.db` (tested against a scratch copy first). 95/95 tests pass.
- [x] **4. Reseed from real data.** D037. Done — `kayam-reseed-from-reference` applied to
  `instance/kayam.db` (tested against a scratch copy first; timestamped `.bak` taken before each
  live run). 9 real jobs + 77 real equipment assets seeded, all unassigned. First pass flagged two
  source-data issues (Roskilde's date order, Silverstone's `t` typo) rather than guessing; the
  owner has since corrected both plus the SOLIDAYS/WILD FIRES venue addresses directly in
  `reference/kay_seed_jobs.csv`, and a corrected re-run now gives all 9 jobs a valid tent — verified
  against a scratch copy, then applied live and spot-checked via the running server. Also fixed a
  reseed idempotency bug found during re-verification (Location clear-by-marker missed
  pre-marker rows from the first live run; now clears by role — everything except the Yard and the
  three demo sites — so re-running after a CSV correction can never collide). 98/98 tests pass.
- [x] **5. Crew Board removal + season board quick-add.** D038. Done — `/planning/crew` deleted
  entirely (route, `CrewPlanningService.board_data()`, `crew_board.html`); its add-activity form
  moved to `/planning/activity/new`, triggered by a "+" in every empty Tentmaster cell on the
  season board, redirecting back to the board's current range on save. Roster board's job-shading
  (`RosterDay.shading_by_tentmaster`) generalised to include `CrewActivity` titles too.
- [x] **6. Season board rebuild.** D038. Done — Milestones/Equipment columns dropped entirely (the
  flow diagram owns equipment); their content plus loads/crew-moves now render as stacked
  `BoardBlock.detail_lines` inside the relevant Tentmaster/Unassigned block, auto-growing
  vertically. Unassigned/Quoted is now a dynamic number of columns via greedy interval-packing
  (`_pack_unassigned_columns()`) — a job keeps one column for the whole span of its unassigned
  phases. Clicking a job fetches `GET /jobs/{id}/summary` (a bare read-only fragment) into the
  side panel, reused by the flow diagram too since it shares `board.js`. The job page splits into
  a read view (`GET /jobs/{id}`, default, zero forms) and the existing `/jobs/{id}/edit` page,
  which now also carries every operational add/remove/edit form that used to be inline. 100/100
  tests pass, ruff/mypy clean, verified live.
- [x] **7. Year-selector default.** D040. Done — `/planning`, `/planning/flow`, and
  `/planning/roster` all default to the current calendar year (Jan 1–Dec 31) when no date params
  are given, via a `year` query param and a `<select>` in each page (auto-submits on change). The
  existing From/To (and roster's Month/Quarter/Season) pickers are untouched and take precedence
  over `year` whenever an explicit start/end is given. 103/103 tests pass, ruff/mypy clean,
  verified live. This closes out the operational model redesign round — all 7 chunks done.

---

# Next session — follow-ups (parked 2026-08-04)

Owner reminders / not yet implemented:

1. **Ancillary kit on season loads (Q043)** — e.g. stake basher added to an early load does **not**
   auto-track through later job→job legs or Yard return. Regen wipes unlocked auto loads.
   Decide: lock-on-edit, carry-ancillaries-with-parent-stock, and/or job-level ancillary
   requirements. See `OPEN_QUESTIONS.md` Q043.
2. (Optional) Surface “this load will be replaced on regen” when editing an unlocked auto load.
3. **Review auto crew moves** — **check what the auto crew-move generator actually does** in
   practice (which Tentmaster legs, dates, modes, what gets wiped on regen). Confirm it matches
   planner expectations or document/fix gaps. Code: `SeasonPlanService._generate_crew_moves`
   in `app/services/season_plan.py`; button **Generate season loads & crew moves**.

---

# First Codex task

Ask Codex to do only this initially:

```text
Read AGENTS.md, SPECIFICATION.md, DECISIONS.md, OPEN_QUESTIONS.md and IMPLEMENTATION_PLAN.md.

Implement Milestone 1 only.

Do not begin later milestones.

Create the project foundation, tests, README, configuration, initial migration setup and local run instructions. Keep the app runnable. Record any assumptions in DECISIONS.md or OPEN_QUESTIONS.md.
```
