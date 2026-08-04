# DECISIONS.md

# Architecture and Product Decision Log

Record durable decisions here. Do not use this file for temporary implementation notes.

---

## D001 — Build a web application from the beginning

**Status:** Accepted  
**Decision:** Build the initial product as a Python web application that runs locally and is accessed through a browser.

**Rationale:**

- Works on macOS, Windows and Linux.
- The same application can later be centrally hosted.
- Avoids maintaining separate desktop and hosted implementations.
- Supports a dense scheduling interface more naturally than a conventional desktop form application.

**Consequences:**

- Initial bind address should be localhost.
- Local packaging can be added later.
- Production deployment should not require a fundamental rewrite.

---

## D002 — Use FastAPI, SQLAlchemy and server-rendered HTML

**Status:** Accepted  
**Decision:** Use FastAPI, SQLAlchemy 2.x, Alembic, Jinja2 and HTMX, with limited vanilla JavaScript.

**Rationale:**

- Provides a modern Python backend.
- Keeps V1 simpler than a separate React frontend and API.
- Allows interactive partial updates.
- Keeps business logic on the server.

**Consequences:**

- JavaScript must not hold authoritative scheduling state.
- React should not be added without a documented need.

---

## D003 — Use SQLite initially

**Status:** Accepted  
**Decision:** Use SQLite for local development and initial operation.

**Rationale:**

- Portable and easy to back up.
- No separate database server required.
- Suitable for a single-user or low-concurrency first version.

**Consequences:**

- Database access must use portable SQLAlchemy constructs.
- Avoid SQLite-specific assumptions.
- Production hosting may later use PostgreSQL or MySQL.

---

## D004 — Preserve the spreadsheet’s continuous seasonal view

**Status:** Accepted  
**Decision:** The principal operational UI will remain a dense, date-oriented seasonal planning board.

**Rationale:**

- The existing workbook lets planners understand the flow of people and equipment across the season.
- Conventional lists and forms alone would remove vital operational context.

**Consequences:**

- Dates run vertically in the main board.
- Crew lanes appear alongside equipment and load lanes.
- The interface may legitimately use a horizontal scrolling region.
- Compact information density is preferred over large dashboard cards.

---

## D005 — Separate jobs from locations

**Status:** Accepted  
**Decision:** A location is a reusable physical place; a job is a commercial and operational event at that place.

**Rationale:**

- The same site may be used repeatedly.
- Access notes, coordinates and HGV restrictions belong to the place.
- Contract dates, tents and revenue belong to the job.

---

## D006 — Model tents as configurable requirements, not fixed assets

**Status:** Accepted  
**Decision:** A tent configuration defines required component types and quantities. A job tent requirement is fulfilled by assigning physical assets.

**Rationale:**

- Tents are temporary assemblies of reusable modular components.
- The same named section can form part of different tents during the season.

**Consequences:**

- Do not create one permanent “tent” asset for each assembled tent.
- Do not hard-code the composition of pole sizes.

---

## D007 — Support individual and quantity-tracked equipment

**Status:** Accepted  
**Decision:** Equipment types specify whether items are individually tracked or quantity-tracked.

**Rationale:**

- Named sections require complete asset history.
- Some ancillary equipment may be managed more practically as quantities.

---

## D008 — Model Tentmaster membership over time

**Status:** Accepted  
**Decision:** Crew members join Tentmasters through date-based membership records.

**Rationale:**

- People move between teams during the season.
- A permanent team foreign key would lose historical accuracy.

---

## D009 — Separate equipment loads from crew movements

**Status:** Accepted  
**Decision:** Equipment transport uses movements and loads. Crew travel uses crew movements and journey legs.

**Rationale:**

- Crew may travel by van, flight, ferry or multiple modes.
- Equipment loads have different capacities, suppliers and costs.

---

## D010 — Treat Oxford Yard as a normal network location

**Status:** Accepted  
**Decision:** Oxford Yard is a location of type `yard`, not a hard-coded special case.

**Rationale:**

- Supports future yards, depots and staging sites.
- Keeps route and location logic generic.

---

## D011 — Use multi-dimensional lorry capacity

**Status:** Accepted  
**Decision:** Lorry types support separate section, pole, ancillary and weight capacities.

**Rationale:**

- Tent equipment can be constrained by shape and stacking before weight.
- One generic capacity score would be too limiting.

**Note:** Exact real-world units remain an open question.

---

## D012 — Distinguish provisional and confirmed planning

**Status:** Accepted  
**Decision:** Commercial status, planning status and allocation strength are separate concepts.

**Rationale:**

- A quoted job may need scenario planning without blocking confirmed work.
- Deposit receipt does not automatically mean every operational detail is approved.

**Consequences:**

- Provisional jobs may create soft holds.
- Approved confirmed assignments may become hard allocations.
- Conflicts must distinguish hard and conditional cases.

---

## D013 — Preserve manual planner control through locks

**Status:** Accepted  
**Decision:** Important assignments, phases and movements can be locked.

**Rationale:**

- Automatic recalculation must not unexpectedly reshuffle the season.
- Experienced planners need authority over final operational decisions.

---

## D014 — Use assisted planning before global optimisation

**Status:** Accepted  
**Decision:** V1 validates manual plans and provides bounded suggestions rather than automatically optimising the whole season.

**Rationale:**

- Full vehicle routing with time windows, crew constraints and multi-leg spare capacity is a complex optimisation problem.
- The product can deliver substantial value before solving it globally.

**V1 progression:**

1. Validate manual loads.
2. Suggest direct movements.
3. Identify obvious spare-capacity opportunities.
4. Support manually approved multi-leg movement.
5. Consider broader optimisation later.

---

## D015 — Separate routing time from operational journey time

**Status:** Accepted  
**Decision:** Store API driving time separately from planned operational duration.

**Rationale:**

Operational duration may include:

- Break and rest allowance
- Ferry check-in
- Border allowance
- Loading
- Unloading
- Contingency

---

## D016 — Use a routing-provider abstraction

**Status:** Accepted  
**Decision:** OpenRouteService is the initial provider, behind a replaceable interface with a manual fallback.

**Rationale:**

- Supports HGV-oriented routing.
- Keeps the application usable without an API key.
- Avoids provider lock-in.

---

## D017 — Store contract revenue and operational costs separately

**Status:** Accepted  
**Decision:** Jobs store contract revenue; labour, travel and transport are separate estimated and actual costs.

**Rationale:**

- Enables estimated and actual margin.
- Avoids the ambiguous phrase “contract cost”.

---

## D018 — Retain the workbook as a reference, not the live data store

**Status:** Accepted  
**Decision:** `DAILY V8.xlsx` remains a visual and migration reference.

**Rationale:**

- Its meaning relies heavily on layout, colours and comments.
- A perfect automatic importer is not a realistic V1 dependency.

**Consequences:**

- Provide a diagnostic workbook-analysis script.
- Do not make normal operation depend on Excel.

---

## D019 — Use timezone-aware operational timestamps

**Status:** Accepted  
**Decision:** Store timezone-aware timestamps and associate locations with timezones.

**Rationale:**

- Work takes place across the UK and continental Europe.
- Local contract times and journey times must remain unambiguous.

---

## D020 — Prefer reversible assumptions

**Status:** Accepted  
**Decision:** When a business rule is unresolved, use a configurable or reversible implementation and document the assumption.

**Rationale:**

- Prevents Codex from silently inventing permanent business behaviour.

---

## D021 — Use migration-owned schema setup and defer domain seed data

**Status:** Accepted  
**Decision:** Alembic is the only mechanism that creates or changes application schema. Application
startup does not call `create_all()`. The Milestone 1 seed command applies migrations but inserts no
business records until the relevant domain models are introduced in later milestones.

**Rationale:**

- Keeps every schema change explicit and reproducible.
- Ensures a clean database and an existing database follow the same upgrade path.
- Satisfies the foundation seed-command requirement without inventing Milestone 2 entities or
  production business data.

**Consequences:**

- Developers must run `alembic upgrade head` or the seed command before using a new database.
- The foundation revision intentionally creates only Alembic’s version table.
- Demonstration records described by the specification were deferred until the Milestone 2 models
  existed; the seed command now creates only clearly labelled examples.

---

## D022 — Share CRUD presentation only for simple administration records

**Status:** Accepted  
**Decision:** Core reference entities use a metadata-driven, server-rendered administration shell
for consistent list, detail, create, edit and delete interactions. Pydantic schemas, services and
database constraints remain entity-specific, and future operational workflows will receive
dedicated routes and templates.

**Rationale:**

- Removes repetitive form and table plumbing across simple reference catalogues.
- Keeps validation and business rules explicit rather than embedding them in template metadata.
- Prevents the generic administration shell from becoming an inappropriate abstraction for jobs,
  confirmations, allocations or planning workflows.

---

## D023 — Store Tentmaster membership as half-open calendar dates

**Status:** Accepted (resolves Q036)  
**Decision:** Tentmaster memberships use calendar dates with an inclusive start and an
**exclusive** end (`end_at` means "first day no longer active"). Open-ended memberships are
permitted, and a crew member cannot belong to overlapping Tentmasters.

**Rationale:**

- Matches the specification’s date-based membership requirement.
- Confirmed with the product owner: crew regularly move between Tentmasters based on staffing
  need, including same-day handovers, and the crew-model rework (job phases deriving headcount
  from `TentmasterMembership`) depends on that being a normal, well-supported operation rather
  than an edge case.

**Consequences:**

- Ending one membership and starting another on the same calendar date is allowed and is the
  expected way to record a same-day crew handover.
- Migration `babee1b7c057` changed the `date_order` check constraint from `end_at >= start_at` to
  `end_at > start_at` and the overlap validation in `app/services/administration.py` to match.

---

## D024 — Normalize operational timestamps to UTC at persistence boundaries

**Status:** Accepted  
**Decision:** Use a SQLAlchemy UTC-aware type that rejects naive datetimes, stores UTC portably in
SQLite, and returns aware UTC values.

**Rationale:** SQLite drops timezone metadata from ordinary datetime columns. Central conversion
prevents naive/aware comparison failures without scattering fixes through planning services.

---

## D025 — Treat generated movements as requirements, not commitments

**Status:** Accepted  
**Decision:** Equipment transition generation creates unlocked records with a generated source and
required status. Assisted suggestions remain transient until a planner explicitly accepts one.

**Consequences:** Generated and suggested transport cannot silently become a confirmed load, and
locked movement/load records are never rewritten automatically.

---

## D026 — Use stored operational allowances with configurable margin bands

**Status:** Accepted pending Q026 and Q027  
**Decision:** Store loading, unloading and contingency minutes separately from cached pure driving
time. Default transition bands are red below six hours, amber from six to 24 hours and green from
24 hours, configurable through settings.

---

## D027 — Build the seasonal board from bounded range queries

**Status:** Accepted  
**Decision:** The combined board loads date-bounded collections and assembles cells in Python. The
browser only filters, highlights and launches server-backed edits.

**Rationale:** This preserves server authority and avoids one database query per board cell.

---

## D028 — Audit operational records automatically in their transaction

**Status:** Accepted  
**Decision:** Create append-only audit rows for important job, assignment, movement, load, crew
travel and cost records in the same SQLAlchemy transaction as the change.

**Consequences:** Local V1 identifies the actor as `local planner`; hosted identity must replace
that label after authentication exists.

---

## D029 — Derive job-phase crew rosters from Tentmaster membership

**Status:** Accepted  
**Decision:** A `JobPhase` assigned to a Tentmaster derives its headcount and named crew from
whoever is an active `TentmasterMembership` member of that Tentmaster during the phase's dates
(minus anyone with an overlapping unavailable-type `CrewAvailability` row), computed by
`app/services/roster.py`. `CrewAssignment` no longer represents "every person on every phase";
it now represents only the exceptions: placeholder/local crew (`placeholder_name`), and named
`ADD` (loan someone onto a phase who isn't currently a derived member, optionally at an overridden
hourly rate) or `EXCLUDE` (remove someone who otherwise would be derived) overrides. The dead
`CrewAssignment.tentmaster_id` tag was removed; `JobPhase.tentmaster_id` is the only authoritative
source.

**Rationale:**

- The previous model required a planner to manually re-create one `CrewAssignment` row per person
  per phase, duplicating what `TentmasterMembership` already recorded, and requiring every row to
  be found and fixed by hand whenever someone changed crews.
- `reference/LOADS 26 V8.xlsx`'s `TM DETAILS` sheet confirms a Tentmaster is a named individual
  leading a crew, not an abstract team, which is why "assign the Tentmaster, derive the crew" is
  the natural unit of planning.

**Consequences:**

- Depends on D023's half-open membership dates so a crew member can move between Tentmasters,
  including same-day, without the derivation breaking.
- `CostingService.crew_work_cost()` and the Conflict Centre both moved from reading
  `CrewAssignment` rows directly to using the same derived roster, so labour cost and crew
  shortfall/receiving-crew warnings stay consistent with what a planner sees on the board.
- A new visual roster board (`/planning/roster`) manages Tentmaster membership over time directly,
  rather than only through the generic administration list.

---

## D030 — Replace named tent configurations with section sequences and a linked-equipment BOM

**Status:** Accepted  
**Decision:** `TentConfiguration`/`TentConfigurationRequirement` (named templates like "Kayam
10-pole" with a flat bill of materials) are removed entirely. A `JobTentRequirement` is now an
ordered sequence of section codes (`JobTentSection`, e.g. K-M-M-M-K), matching the hyphen-
delimited notation already used in the business's own load-content lists
(`reference/LOADS 26 V8.xlsx`). Poles are derived, not entered: `TentFamily` stores a linear
formula (`poles = sections × pole_count_multiplier + pole_count_offset`, defaulting to Kayam's
confirmed sections×2−2) and which `EquipmentType` fulfils that derived requirement. Equipment
types also carry a `pack_size` (physical units per tracked asset, e.g. 2 for a pole type tracked
as a pair). A new self-referential `EquipmentLink` table (parent/child equipment type + quantity)
replaces the flat BOM with a recursive cascade — booking a section or a derived pole can imply
further equipment (bale rings, side poles, anchor stillages, side guys, Tifors), recursively,
cycle-guarded. `EquipmentType.code` was rebuilt around the business's real letter-code vocabulary
(K, M, m, S, T, SC, V, VOE, VNE, P, X, plus non-sequence ancillary types AD/SB/VB/RD/CT) instead
of generic category names (END/MIDDLE/POLE/ANCHOR_SET/ANCILLARY_KIT); codes are case-sensitive on
purpose since M (20m middle) and m (15m middle) are genuinely different types.

**Rationale:**

- The owner corrected this directly: many different section combinations produce the same pole
  count (e.g. a run of 8 poles could be KKKKMMM or several other combinations), so naming tents by
  pole count was never how the business actually thinks about or books them.
- `reference/LOADS 26 V8.xlsx`'s asset codes (K1, M21, P4, ...) already use exactly this
  letter-code vocabulary; the previous generic EquipmentType codes were a separate, hand-maintained
  mapping in the seed script, decoupled from the model.
- Only two linked-equipment ratios are actually confirmed by the owner (M → 2 bale rings; P → 2
  side guys + 2× 1.5t Tifors) — seeded as the only two `EquipmentLink` rows; every other section
  type's links are deliberately left unconfigured rather than guessed (see OPEN_QUESTIONS.md).

**Consequences:**

- `JobService.regenerate_requirements()`'s GENERATED/MANUAL preservation rule is unchanged in
  spirit — only how the GENERATED totals are computed changed, from a flat per-template lookup to
  recursive expansion (`_expand_tent_requirement`/`_expand_links`).
- The job detail page now shows a "Loading list" (sections + derived poles — the visible/big items
  a planner actually diagrams) separate from a collapsed "linked equipment" detail view, matching
  the owner's own framing that a load only needs to list the big items.
- `TentFamily` absorbed `TentConfiguration`'s old per-size build/strike-hours and crew defaults as
  family-level defaults (still overridable per job), since size is now derived from the sequence
  rather than a named template.
- This is a genuine schema replacement, not a parallel system — migration `47d2b2d36c51`
  re-points existing `EquipmentAsset` rows at their renamed types in place (no FK remapping needed)
  and reconstructs existing jobs' section sequences from their old named configuration's BOM before
  dropping the old tables.

---

## D031 — Season board: contiguous blocks, an unassigned/quoted lane, and a split operations column

**Status:** Accepted  
**Decision:** The combined board (`/planning`) keeps D027's one-row-per-day, bounded-query
architecture, but changes what each row shows:

- `BoardBlock` gained a `segment` field (`solo`/`start`/`mid`/`end`), computed per multi-day
  record from its own actual start/end dates, not the visible board range — a block that started
  or continues past the edge of the requested date window correctly renders as `mid`/`end` rather
  than getting an artificial "start," since it genuinely is continuing from off-screen. CSS uses
  this to remove the internal gap between a block and the row below/above it when they belong to
  the same record, so a multi-day job phase or activity reads as one continuous bar down a
  Tentmaster's column instead of the same label repeated as a flag on every day.
- Job phases with no `tentmaster_id` no longer render as a bare, context-free block in a shared
  column — they get their own "Unassigned / quoted" lane, positioned like an extra Tentmaster
  column, so a planner can see how an unconfirmed or not-yet-crewed job would sit alongside
  confirmed work before committing it to a Tentmaster.
- The old single "Jobs & equipment" column mixed three unrelated things (job MUST BE UP/STRIKE
  milestones, a *duplicate* copy of every phase block already shown in its Tentmaster column, and
  equipment-asset movements) into one list. It's replaced with two single-purpose columns,
  "Milestones" and "Equipment" — phase blocks are no longer duplicated into either, since they now
  render exactly once (in their Tentmaster's column or the unassigned lane).

**Rationale:** Direct owner feedback: the board "needs to look much more like the sheet, so we can
see large blocks in the Tentmaster columns rather than just day flags," the old "Jobs and
Equipment" column was "confusing and weird," and there was no way to place an unconfirmed/quoted
job on the board to see it in context without assigning it to a Tentmaster.

**Consequences:**

- `BoardDay` changed shape: `operations` (mixed) was replaced by `unassigned`, `milestones` and
  `equipment` (each single-purpose); `tentmasters` is unchanged in shape but its blocks now carry
  `segment`.
- No schema/migration change — this is presentation-layer only (`BoardService`, the board
  template, and `app.css`); `JobPhase.tentmaster_id` was already nullable.
- The per-day-row table structure is deliberately preserved rather than rebuilt as a true Gantt
  grid (absolute-positioned multi-day spans) — that would be a much larger rewrite for a marginal
  visual gain over the CSS-merge approach, and would complicate the sticky date column.

---

## D032 — Render the loads/equipment flow diagram as a board-shaped table with an SVG line overlay

**Status:** Accepted (revised — see history below)  
**Decision:** `/planning/flow` (`FlowService`, `app/services/flow.py`) is laid out exactly like the
season board: dates run down the side, one row per day, sticky date column. Columns are
*locations* instead of Tentmasters — every location with an active job or an equipment movement in
the range gets a column (yard/depot first, then sites alphabetically). Each location's column
shows a block for every day a job occupies that site (job code + booked tent section sequence,
e.g. `KMMMK`), reusing the season board's own `.season-block`/contiguous-segment CSS so a job's
whole stay renders as one merged bar exactly like a Tentmaster's job block. A load's journey is
drawn as a line in an absolutely-positioned SVG overlay on top of the table, from the origin
column at its depart date to the destination column at its arrival date — a direct site-to-site
move draws as a line that never touches the yard column, matching what actually happened. The
table uses `table-layout: fixed` with explicit column/row pixel sizes so the server-computed SVG
coordinates line up exactly with the rendered cells.

**Rationale (why this replaced the first version):** The first cut of this page (a horizontal
Marey/space-time diagram — locations as lanes, time left-to-right) was accepted and shipped, but
the owner asked for another pass specifically because it didn't look like the sheet: they wanted
"dates down the side (like the original sheet)" and "blocks which show the location (job), with
sections moving in and out" — i.e. the same date-vertical, entity-column shape as the season board
itself, not a sideways timeline. This version delivers that directly, and by reusing the season
board's block/segment CSS wholesale, a job's site occupancy reads exactly like a Tentmaster's job
block does on the season board — one consistent visual language across both pages.

**Consequences:**

- No schema change — still reads existing `Job`/`EquipmentMovement`/`Load`/`LoadItem`/`Location`
  data only, via the same bounded, eager-loaded query pattern as `BoardService` (D027).
- `FlowService` now also queries `Job` directly (not just movements) so a job's site shows its
  occupancy block on every day it's there, even on a week with no load transiting — matching the
  reference sheet's own "BUILD/BUILD/BUILD..." repeated-block convention for a Tentmaster's column.
- The flow page reuses the season board's toolbar and `board.js` wholesale for its location-block
  cells (filter, zoom, click-to-highlight all work identically) since the DOM shape is now
  identical (`<a class="season-block">` in a `<td>`); a small `flow.js` handles clicks on the SVG
  line edges specifically and shares the same side panel.
- Still a read-only visualization — a click opens the job or the movement's first load for editing,
  consistent with the season board's own pattern rather than inventing in-diagram editing.

---

## D033 — Season board and roster refinements: fill, detail, drag-and-drop, job-context shading

**Status:** Accepted  
**Decision:** Four follow-up refinements to D031's season board and the crew roster board, all
direct owner feedback after using both pages:

1. **Blocks fill the day vertically.** Team/unassigned `<td>` cells (`class="lane-cell"`) use
   `display: flex; flex-direction: column` with `.season-block { flex: 1 1 auto }`, so a block
   stretches to the row's actual height instead of leaving whitespace when another column in the
   same row is taller. Scoped to lane cells only (not Milestones/Equipment/Movements), so short
   flag-like blocks elsewhere keep their compact size.
2. **Richer job block detail.** A job phase's block subtitle now includes the job's booked tent
   section sequence (`_tent_summary()`) and, on the day a phase actually starts or ends, an
   `UP hh:mm` / `DN hh:mm` marker — mirroring the reference `DAILY` sheet's own convention of
   flagging exact up/down times inline in a Tentmaster's column, rather than only in a separate
   Milestones column.
3. **Drag-and-drop job reassignment.** A job block can be dragged onto a different Tentmaster's
   column (or the Unassigned lane) to reassign `JobPhase.tentmaster_id`, via a new
   `JobService.reassign_phase_tentmaster()` (deliberately not the full `update_phase()` validation
   path — it only touches `tentmaster_id`, rejects locked phases, and does not block on double-
   booking, since that's reported on the conflicts page rather than blocked at write time (D013).
   Mirrors the roster board's existing crew-member drag-and-drop (`fetch` + redirect-follow), new
   route `POST /planning/move-phase`.
4. **Roster board job-context shading.** Each Tentmaster's roster column tints amber
   (`.roster-drop-cell.has-job`) on dates they're booked on a job, with the job code shown inline,
   so a planner can see the season's shape — which Tentmasters are already committed when — while
   dragging crew between teams. Computed in `RosterBoardService.build()` from `JobPhase` rows
   overlapping the visible range; chosen over two alternatives (a separate per-Tentmaster
   "job" column, or an independent season-strip) because it puts the information exactly where the
   planner is already looking, with no new columns to scan.

**Rationale:** All four came directly from the owner using the pages built under D031 — they are
incremental UX corrections, not new architectural decisions, but are recorded here because two of
them (drag-and-drop reassignment, the boundary-time detail convention) introduce a genuinely new
interaction/service method that later work should know about rather than rediscover.

**Consequences:**

- No schema change for any of the four.
- `BoardBlock` gained `phase_id` (needed so a dragged block's `<a>` knows which `JobPhase` to
  reassign) — the same field flow diagram's `FlowCellBlock` deliberately does *not* need, since its
  blocks represent job-site occupancy, not a draggable phase assignment.
- The board's `phases` query now also eager-loads `Job.tent_requirements` (sections + equipment
  type) so the per-day tent summary is computed once per job, not per day, staying within the
  existing bounded-query budget (`test_board_uses_bounded_queries` still passes unchanged).

---

## D034 — Operational-model redesign round (2026-08-03), Chunk 1: crew availability moves onto the crew member's own page

**Status:** Accepted  
**Decision:** This is the first of several chunks in a larger post-usage redesign round (crew
availability relocation → roster drag-and-drop cascade fix → operational phases rework → reseed →
crew board removal → season board rebuild → year-selector default), sequenced so each chunk lands
and gets checked against the running app before the next starts, rather than as one large change.

Chunk 1: `CrewAvailability` (short leave/unavailable periods) and `CrewAvailabilityWindow`
(longer season-contract windows) are no longer browsable as their own top-level admin sections.
`EntityDefinition` gained a `hidden: bool` flag (default `False`); both entities set it `True`,
which excludes them from `grouped_entities()` (and therefore the `/admin` index) while leaving
their generic CRUD routes (`/admin/crew-availability/...`, `/admin/crew-availability-windows/...`)
fully intact underneath. `/admin/crew-members/{id}/edit` now renders a bespoke nested section
listing both, with inline add-forms that pre-fill `crew_member_id` and post to those same generic
routes with a new `redirect_to` field so the browser lands back on the crew member's own page
instead of the (now-unlisted) entity's own detail page. `create_record`/`update_record`/
`delete_record` in `app/routes/admin.py` accept this optional `redirect_to`, restricted via
`_redirect_target()` to paths starting with `/admin/` to avoid an open redirect.

**Rationale:** Direct owner feedback: availability is something you set *for a person*, not a
generic list you browse independently, so it belongs on that person's own record. Reusing the
existing generic CRUD (rather than writing bespoke create/update/delete logic for two more entity
types) keeps this a presentation-layer change — same validation, same models, same migrations
untouched — while still meeting the "edit it from the crew member's page" requirement.

**Consequences:**

- This is a genuine, documented exception to D022 ("share CRUD presentation only for simple
  administration records") — availability is simple, but its natural editing context is nested
  inside another record rather than a flat list.
- The generic entity is still fully reachable by URL (`/admin/crew-availability`) for anyone who
  bookmarks it or for tests that iterate `ENTITY_DEFINITIONS` directly — only navigation/discovery
  changed, not the underlying capability.
- `redirect_to` on create/update is a form field (posted alongside the record's own fields); on
  delete it's a query parameter, since delete forms carry no other data.

---

## D035 — Operational-model redesign round, Chunk 2: roster move semantics and unavailable-but-assigned rendering

**Status:** Accepted  
**Decision:** Two fixes to `RosterBoardService` from real drag-and-drop usage:

1. `move_crew_member()` no longer always creates an open-ended (`end_at=None`) membership when
   assigning someone to a new Tentmaster. It now looks up whether that crew member already has a
   *future* `TentmasterMembership` (`start_at > effective_date`) and, if so, caps the new segment's
   `end_at` at that future segment's `start_at` — the future assignment then resumes automatically
   once the new segment ends, instead of the move being wrongly rejected as a conflict (the actual
   bug: the code always tried to insert an open-ended row, which genuinely does overlap any
   already-scheduled future row, so `_validate_membership_overlap` was correctly rejecting an
   incorrectly-shaped request). Moving to **Unassigned** is treated differently on purpose: it
   deletes *every* future segment (`start_at > effective_date`), not just the nearest one, since
   "unassigned" has no natural resume point — that's the one case where the whole future timeline
   for that person should genuinely be cleared.
2. `RosterDay.members_by_tentmaster` now holds `RosterMember(member, available)` instead of a bare
   `CrewMember` list. A crew member who's on a Tentmaster's active `TentmasterMembership` but marked
   unavailable that day (via `CrewAvailabilityWindow`) now stays visible in that Tentmaster's column
   — rendered greyed (`.roster-chip-unavailable`) — instead of vanishing from the board entirely,
   while still being excluded from the Unassigned lane (they're not unassigned) and not contributing
   to headcount.

**Rationale:** Direct owner feedback after using the roster board's drag-and-drop: dragging someone
onto a Tentmaster before an already-scheduled future assignment always produced a conflict error
that made no real-world sense, and an unavailable crew member disappearing entirely (rather than
showing as "still on this team, just not available today") lost information a planner needs.

**Consequences:**

- No schema change — both fixes are entirely in `RosterBoardService`/its template.
- `tests/test_roster_board.py` gained
  `test_move_crew_member_slots_in_before_existing_future_membership` and
  `test_move_crew_member_to_unassigned_clears_future_memberships`, reproducing the exact reported
  scenarios; `test_roster_board_hides_member_outside_availability_window` was renamed to
  `test_roster_board_greys_out_member_outside_availability_window` and its assertions inverted to
  match the new (correct) behavior.
- The "prefer a form" manual-move dropdown and the drag-and-drop chip rendering both updated for
  the `RosterMember` wrapper (`entry.member.id`/`entry.member.name` instead of direct attribute
  access).

---

## D036 — Operational-model redesign round, Chunk 3: Build/Up/Break phases, per-tent contract dates, local crew

**Status:** Accepted  
**Decision:** The biggest single chunk of this round. Several related changes, all shipped
together since they're structurally entangled:

1. `PhaseType` simplifies to `BUILD`, `UP`, `BREAK` (`OTHER` kept as a manual-only escape hatch;
   `SITE_PREP`/`HANDOVER`/`SHOW`/`MAINTENANCE`/`STRIKE`/`CLEAR_SITE` removed — none but `SHOW` and
   `STRIKE` were ever actually auto-generated).
2. Contract Up/Down dates move from `Job` (one pair, job-wide) to `JobTentRequirement`
   (`contracted_up_at`/`contracted_down_at`, required, one pair per tent) — a job with multiple
   tents can have different contract dates per tent. `Job.site_access_at` (now optional) and
   `site_clear_by` remain the only genuinely job-wide dates.
3. Each tent gets its own `UP` `JobPhase` (`job_tent_requirement_id` set, enforced by two
   `CheckConstraint`s so only `UP` phases reference a tent and every `UP` phase references one).
   Up phases are freely addable/removable/reassignable between Tentmasters — a crew handover
   mid-contract, overlap allowed on the handover day — but `JobService._validate_up_within_contract`
   rejects any Up phase whose dates fall outside its tent's fixed contract window. `BUILD`/`BREAK`
   stay job-level (`job_tent_requirement_id` null) since the same crew typically builds/strikes
   every tent on a job together.
4. Phases are no longer a continuously re-synced desired state (the old `generate_phases()`,
   called on every job save, deleted and recreated GENERATED phases to match current job fields).
   `JobService._seed_phases_for_new_tent()` runs once, when a tent is added: always seeds that
   tent's Up phase; seeds the job's Build (Up − 5 days) and Break (Down + 3 days) if it's the
   job's first tent; seeds an extra Build segment between an already-existing tent's Up and a
   later-added tent's Up. From then on the planner freely edits via new `add_phase()`/
   `delete_phase()`/`update_phase()` — seeding is a starting point, not an invariant the system
   re-enforces.
5. The entire crew-override mechanism (`CrewAssignment`/`OverrideType` — ADD-loan, EXCLUDE,
   placeholder) is deleted. Local/hired crew becomes `LocalCrewBooking` (job-level, date-ranged,
   headcount only, no name) — `roster.phase_roster()` now adds a job's bookings that overlap a
   phase's dates directly, replacing the old placeholder-count-plus-override logic entirely.
6. A planner can manually book non-section tracked equipment (stake basher, crew tent, ...) via
   `JobService.add_ancillary_equipment()` — no stage picker; defaults internally to
   `BuildStage.COMPLETION_AND_ANCILLARY` and tops up an existing manual line of the same type
   rather than creating a duplicate (`JobEquipmentRequirement`'s unique constraint is
   job+type+stage+source).

**Rationale:** Direct owner correction: contract Up/Down genuinely varies per tent on the same
job, so it was wrong to model it as one job-wide pair; "Build"/"Show"/"Strike" terminology should
match what the business actually calls it (Build/Up/Break, consistently); the old override
mechanism was "too complicated" for what's actually needed (anonymous headcount over a date
range, not named per-person exceptions); and phases needed to stop being silently re-generated
out from under manual edits every time a job was saved.

**Consequences:**

- Migration `e71a563ebf28`: backfills every tent's contract dates from its job's old
  `must_be_up_at`/`strike_available_at` (the old model's one shared pair); reclassifies existing
  `SHOW` phases to `UP` (tied to the job's first/lowest-id tent — the old model had no per-tent
  distinction to recover) and `STRIKE` to `BREAK`; converts real placeholder `CrewAssignment` rows
  and non-zero `local_crew_supplied` values into `LocalCrewBooking` rows rather than silently
  dropping them; drops `crew_assignments` entirely (named ADD/EXCLUDE override rows have no home
  in the new model and are **not** migrated — confirmed against `instance/kayam.db` before writing
  the migration that the only such rows were test/demo artifacts from earlier live-testing, not
  real operational data). Tested against both a fresh database and a scratch copy of the real one
  before being applied live, per established practice.
- `JobEquipmentRequirement.required_on_site_at`/`releasable_at` (both `GENERATED` and manually
  booked ancillary items) now derive from `JobService._requirement_window()` — the earliest tent's
  Build start to the latest tent's Break end across the whole job — instead of the old
  `job.site_access_at`/`job.strike_available_at`.
- `EquipmentPlanningService.derive_state()`'s "in_use" check now uses the specific tent's contract
  window when an assignment's requirement is tied to one, falling back to any of the job's tents'
  windows otherwise (ancillary equipment isn't tied to a specific tent).
- Every downstream consumer of the old fields updated: `board.py` (milestones now per-tent Up/Down
  markers; the loads-to-job matching heuristic uses the same aggregate window), `flow.py` (job
  query now joins `JobTentRequirement` and filters on the same expanded window), `costing.py`
  (labour cost no longer has an override-rate branch; local crew is deliberately excluded from
  labour cost — it's anonymous headcount with no rate, not named people), `conflicts.py` (the
  ADD-override conflict-check block removed entirely).
- `jobs/detail.html` gained: per-tent contract date display (read-only) and add-form, an add/
  remove-phase form (still inline-editable for now — the read/edit page split is chunk 6), a local
  crew add/remove list, and a manual ancillary-equipment booking form. The now-dead
  `/jobs/{id}/phases/{id}/crew/new` route and `crew_assignment_form.html` template are deleted.

---

## D037 — Operational-model redesign round, Chunk 4: reseed from the real jobs CSV and stock list

**Status:** Accepted  
**Decision:** New command `app/commands/reseed_from_reference.py` (`kayam-reseed-from-reference`)
clears operational/demo data and reloads it from `reference/kay_seed_jobs.csv` (9 real jobs) and
`reference/kay_seed_stock.txt` (77 real equipment assets, copied in from the owner's stock list so
the command doesn't depend on a path outside the repo). Cleared: every `EquipmentMovement`
(cascades `Load`/`LoadItem`), `CrewMovement` (cascades legs/passengers), `Job` (cascades phases/
tent requirements/equipment requirements/assignments/local crew bookings), `EquipmentAsset`, and
the three demo-only site `Location` rows; `LoadCostAllocation` is deleted first since it
references `Load`/`Job` without `ON DELETE CASCADE`. Kept untouched: the equipment taxonomy,
crew/Tentmaster reference data, "Oxford Yard", and other admin/logistics reference tables — this
is a data-scope clear, not a full wipe. Every seeded job lands with **no Tentmaster on any
phase** (Unassigned/Quoted), by request, so allocation can be tried from a clean slate; no loads
or equipment assignments are seeded.

Bundled in the same chunk: a small preceding migration (`99fa517eb199`) corrects
`EquipmentType.code` for Siam End from `'S'` to `'s'` — the real stock list, the real jobs CSV,
and (on closer inspection) the original `LOADS 26 V8.xlsx` reference workbook's own "Contents"
notation all consistently use lowercase `s`; the uppercase `S` from the original taxonomy pass was
wrong.

**Rationale:** The owner wanted to try real crew allocation against real job data instead of
placeholder demo jobs, explicitly scoped down to "just jobs and required sections, perhaps some
crew" — no loads/equipment-assignments yet, since that's further down the roadmap (the automatic
load-design engine).

**Consequences:**

- The first pass through the source CSV surfaced two real data problems, caught rather than
  silently guessed at: ROSKILDE's Down date (07 Jun) was before its Up date (23 Jun); SILVERSTONE's
  section sequence contained a lowercase `t`, which isn't a valid code (only uppercase `T`, Kayam
  Triangle, exists). Both jobs were created with their location but no tent — visibly flagged rather
  than fixed to a guessed value. **The owner has since corrected both** (Roskilde Down = 07 Jul;
  Silverstone's `t` → `T`) directly in `reference/kay_seed_jobs.csv`, and a re-run of the reseed
  now gives all 9 jobs a valid tent requirement.
- The owner also corrected two addresses that were wrong in the original CSV import: both
  "SOLIDAYS" rows are genuinely the same venue (Longchamp Racecourse, Paris — two tents, not two
  sites) and now share a single `Location` row (`SOLIDAYS`/`SOLIDAYS-2` jobs, same `location_id`);
  "WILD FIRES" is genuinely at Wiston Estate, West Sussex (not Paris, as the CSV briefly and
  incorrectly held). Venue de-duplication is keyed off the first comma-segment of the site address
  via an in-loop `locations_by_venue` cache in `reseed_jobs()`.
- `Job.commercial_status` defaults to `QUOTED` and `customer_name` to `"TBC"` for every seeded
  job — neither is in the source CSV, and both are honestly-labelled placeholders rather than
  guesses.
- Valhalla-family jobs (`CATALYST`, `READING`, `ROSKILDE` — all `VOE`/`V` sequences) don't get
  derived poles, since `TentFamily.pole_equipment_type_id` for Valhalla is still unconfigured
  (`OPEN_QUESTIONS.md` Q040) — expected, not a reseed bug.
- `clear_operational_data()` deletes every `Location` except the Yard and the three demo-only
  sites (rather than matching on a marker string), so the command is safely re-runnable — an
  earlier version matched deleted-locations by an `access_notes` marker tag, which broke on a
  second real-world run because locations created by the *first* live run predated the marker and
  weren't caught, causing a `UNIQUE constraint failed: locations.name` collision. Since only the
  reseed command ever creates venue `Location` rows, exclusion-by-role is both simpler and immune
  to this class of bug.
- Tested against a scratch copy of `instance/kayam.db` before being applied live, per established
  practice (including a second scratch run to confirm the fixed clear step is idempotent); a
  timestamped `instance/kayam.db.pre-reseed*.bak` was also taken before each live application.
- Tests in `tests/test_reseed_from_reference.py` cover the clear step preserving reference data,
  the stock-code-to-equipment-type prefix mapping (including the `s`/`sc`, `V`/`VNE`/`VOE`/`Vb`
  disambiguation), that all 9 jobs now get a valid tent, that both SOLIDAYS jobs share one
  Location, and that running clear+reseed twice in a row doesn't collide.

---

## D038 — Operational-model redesign round, Chunks 5 & 6: Crew Board removal and season board rebuild

**Status:** Accepted  
**Decision:** Two more chunks of the round, landed together since the season board rebuild
subsumed most of the Crew Board's own reason to exist:

1. **Crew Board removed.** `/planning/crew` (route, service method `CrewPlanningService.board_data()`,
   and `crew_board.html`) is deleted outright. Its one genuinely useful action — adding a
   `CrewActivity` for a Tentmaster over a date range — moves onto the season board itself: a "+"
   link in every empty Tentmaster cell opens the same form (now at `GET/POST
   /planning/activity/new`, renamed from `/planning/crew/activity/new`), which redirects back to
   the season board's current date range on save instead of the deleted crew board. The roster
   board's amber job-context shading (`RosterDay.shading_by_tentmaster`, renamed from
   `jobs_by_tentmaster`) now also picks up `CrewActivity` titles, not just job codes, so a
   Tentmaster's cell shows *why* they're shaded either way.
2. **Season board rebuilt** (`app/services/board.py`, `combined_board.html`): the "Milestones" and
   "Equipment" side columns from D031 are dropped entirely — equipment-asset movement is now
   exclusively the flow diagram's job (D032's own rationale, just followed through here). What
   used to live in those two columns, plus loads and crew-move movements that used to sit in a
   third "Movements & loads" column, is instead folded into **stacked lines inside the relevant
   Tentmaster or Unassigned block itself** (`BoardBlock.detail_lines`): contract Up/Down markers
   (an Up phase shows only its own tent's; Build/Break phases, being job-wide, show every tent's),
   local-crew arrive/depart, and any load or crew-move overlapping that job/Tentmaster that day.
   Blocks auto-grow vertically to fit — a tall day is a legitimately busy day, not a layout bug.
   "Unassigned / quoted" changes from one flat lane to a **dynamic number of columns**, computed
   once per board build via greedy interval-graph colouring over each job's unassigned-phase span
   (`_pack_unassigned_columns()`) — a job keeps one column for the whole run of its unassigned
   phases, and the board only opens as many concurrent columns as the date range actually needs.
3. **Job side panel.** Clicking a job block on the season board (or the flow diagram, which reuses
   the same `board.js`) now fetches `GET /jobs/{id}/summary` — a bare HTML fragment, no
   `base.html` chrome — and injects it into the existing side panel, instead of just echoing the
   block's own label/subtitle text. The fragment is the same read-only content as the job page
   itself, plus an Edit button.
4. **Job page splits into read and edit.** `GET /jobs/{id}` (and the new summary fragment) render
   a shared `jobs/_read.html` partial with every section read-only — no forms, no delete buttons,
   no assignment-approval checkboxes. Every add/remove/edit action that used to be inline on that
   page (tent requirements, phases, local crew, ancillary equipment booking, equipment-assignment
   approval) moves onto the existing `/jobs/{id}/edit` page, appended after its Commercial/
   Location/Dates/Operations fields — reusing the exact same POST endpoints, just relocated in the
   UI. `/jobs/new` reuses the same template; the operational sections are guarded by `{% if job_id
   %}` since a new job has none of that yet.

**Rationale:** Direct continuation of the plan recorded in `IMPLEMENTATION_PLAN.md` chunks 5–6:
one page to both see and add crew work rather than two overlapping ones; the season board reading
"more like the sheet" by showing a Tentmaster's whole day as one block instead of scattering
related facts across side columns; jobs becoming clickable without leaving the board; and the job
page no longer being editable-by-default, which was flagged as a risk once the board started
linking into it more often.

**Consequences:**

- `CrewPlanningService.board_data()` deleted (dead code once the crew board route was gone); its
  sibling `daily_totals()`/`daily_totals_by_tentmaster()` methods are kept — genuinely useful,
  independently tested, no longer route-driven.
- `app/services/conflicts.py`'s Tentmaster-double-booking conflict link and `board.py`'s activity
  block link both repointed from the deleted `/planning/crew` to `/planning`.
- A load or crew-move now only appears on the season board if it's attributable to a job with a
  visible phase block that day (via the same destination/arrival-window heuristic D027 already
  used) — e.g. a return-to-yard load, which has no job at the yard end, no longer shows on the
  season board at all. This is deliberate (`/planning/flow` is the complete logistics picture now)
  but is a real visibility change worth knowing about if a load "disappears" from the board.
  Likewise a contract Up/Down milestone with no phase block active anywhere that day (a data
  anomaly — the auto-seeded Up phase would normally cover it) has nowhere to render and is
  silently omitted; not expected to occur in practice, not solved here.
- New tests: `test_roster_board_shows_activity_label_for_booked_tentmaster`
  (`tests/test_roster_board.py`), `test_job_page_splits_into_read_view_and_edit_surface`
  (`tests/test_operational_routes.py`), plus `test_board_conflicts.py` updated for the new
  `BoardBlock.detail_lines`/dynamic `BoardDay.unassigned` shape. 100/100 tests pass, ruff/mypy
  clean, verified live against the running dev server (quick-add activity round-trip, job side
  panel fragment fetch, read page has zero edit forms, edit page has all of them).

---

## D039 — Real per-section linked-equipment parts matrix from `reference/kay.parts.csv`

**Status:** Accepted  
**Decision:** 22 new `EquipmentType` rows (category `linked`) and ~91 `EquipmentLink` ratios,
transcribed verbatim from the owner-supplied `reference/kay.parts.csv` stock sheet, covering every
Kayam-family section/pole code (K, m, M, T, SC, s, P, X) — guys, tifors, cables, stretchers, walls,
stakes, ratchets, caps, base plates, hinges, and a stage-cover rigging box. Defined as
`LINKED_PARTS_MATRIX` in `app/commands/seed.py`, applied via a new `_ensure_linked_parts()` helper
(also called from `seed_development_data()` for fresh databases) and a new standalone command,
`kayam-sync-equipment-taxonomy` (`app/commands/sync_equipment_taxonomy.py`), for pushing taxonomy-
only updates onto an already-seeded database like `instance/kayam.db` without touching jobs, crew,
or any operational data — `kayam-seed`'s own `main()` isn't usable there since it also (re)seeds
demo jobs/locations.

**Rationale:** Q038/Q039 had been left deliberately unconfigured pending real data rather than
guessed; this CSV is that real data, covering every section type instead of just the two ratios
(M→Bale Ring, P→Side Guy/Tifor) confirmed earlier.

**Consequences:**

- `SIDE_POLE` and `BALE_RING` reused their pre-existing codes (the CSV's "Sidepole"/"Balerings"
  rows unambiguously match, and `Balerings`' M=2 exactly confirms the ratio already configured);
  every other row is a genuinely new type.
- The CSV's "Standard Guys" (P=3, X=3) and "1.6/3.2 Ton Tirfor" (P=3 each) don't cleanly match the
  pre-existing placeholder `SIDE_GUY`/`TIFOR_1_5T` types (P=2 each) — left as separate types rather
  than merged, since it isn't certain they're the same physical item; flagged in `OPEN_QUESTIONS.md`
  Q039 for the owner to confirm whether the old placeholders should be deactivated.
- `default_build_stage` per part (`POLES_AND_ANCHORS` for rigging hardware, `MAIN_SECTIONS` for
  section-cladding hardware, `COMPLETION_AND_ANCILLARY` for flags/stage-cover rigging) is inferred
  from what each part physically is, mirroring the convention already used for
  `SIDE_POLE`/`SIDE_GUY`/`BALE_RING`/`ANCHOR_STILLAGE` — not stated in the CSV itself.
- Adding a `K`→`BALE_RING` link (the CSV gives K=1, previously only `M`→`BALE_RING` existed)
  changed the expected totals in two existing tests
  (`test_linked_equipment_cascades_from_sections_and_poles`,
  `test_expansion_guards_against_indirect_equipment_link_cycle`) — updated with worked-out
  explanations rather than just bumping the numbers blind.
- Tested against a scratch copy of `instance/kayam.db` (115 new records, then 0 on a second run —
  confirmed idempotent) before applying live, per established practice; all 9 reseeded jobs'
  `JobEquipmentRequirement` rows were then regenerated (`JobService.regenerate_requirements()`,
  safe here since none had manual items or physical assignments yet) so the new parts actually
  show up on their loading lists immediately rather than only on the next edit.
- `ANCHOR_STILLAGE` has no equivalent row in the CSV at all — still fully unconfigured (Q038).
  Valhalla (`V`/`VOE`/`VNE`) has no equivalent CSV either — still fully unconfigured (Q039/Q040).
- Lorry-loading capacity data the owner supplied in the same message (curtainsider/flatbed point
  capacity, points-per-section-type, three Valhalla flatbed-count examples) is **not** implemented
  by this decision — recorded verbatim in `OPEN_QUESTIONS.md` Q042 for the load-design engine
  design conversation instead, including an unconfirmed attempted formula for the Valhalla
  examples that explicitly should not be built against without the owner's sign-off.
- 100/100 tests pass, ruff/mypy clean.

---

## D040 — Operational-model redesign round, Chunk 7 (final): year-selector default

**Status:** Accepted  
**Decision:** `/planning`, `/planning/flow`, and `/planning/roster` all default their date range
to the current calendar year (Jan 1–Dec 31) instead of their previous ad hoc defaults (season
board/flow: 1 April + 183 days; roster: start of current month + a quarter). A `year` query param,
driven by a `<select>` that auto-submits on change, sets the range to that year's Jan 1–Dec 31.
The existing From/To pickers (and roster's Month/Quarter/Season range selector) are unchanged and
take precedence whenever an explicit `start`/`end` (or `start`/`days` for roster) is given — `year`
only supplies the default when nothing more specific is present.

**Rationale:** Direct owner feedback that the roster board "is still defaulting to Quarter from
beginning of this month," flagged during 2026-08-03 live testing. This was the last of the 7
chunks in the operational model redesign round.

**Consequences:**

- `app/routes/board.py`'s `_range()` helper now takes a `year` parameter; roster's route builds
  its own equivalent inline (it works in `days`-from-`start` terms, not `start`/`end`, so needed
  its own leap-year-correct day count rather than reusing `_range()` directly).
- New tests in `tests/test_operational_routes.py` cover the default-to-current-year behaviour on
  all three pages, an explicit `year` override, and that an explicit start/end range still wins
  over `year` when both could apply.
- 103/103 tests pass, ruff/mypy clean, verified live (`data-board-start`/`data-board-end` on the
  season board, the From input on the flow diagram, and the roster's start date all confirmed to
  read the current year with no params; `?year=2027` and an explicit `start`/`end` range both
  confirmed to override it correctly).
- This closes the operational model redesign round — all 7 chunks (D034–D040) done.

---

## D041 — Fix: `display: flex` on `<td class="lane-cell">` was breaking the season board and flow diagram's table layout

**Status:** Accepted  
**Decision:** Removed `.season-board td.lane-cell { display: flex; flex-direction: column; }` and
its paired `.season-block { flex: 1 1 auto; }` override entirely. `.season-block` is already
`display: block`, so it stacks correctly inside a normal table cell without needing the cell
itself to be a flex container.

**Rationale:** Setting `display: flex` directly on a `<td>` is a known CSS trap — per the CSS
Display spec, a table cell whose `display` is overridden away from `table-cell` stops
participating in the table's column-layout algorithm. The owner reported this live (screenshot,
incognito window, so not a caching issue): the season board's header row rendered four correctly-
separated Tentmaster columns, but every body row's content — all four Tentmasters' "+" links and
every Unassigned block — collapsed into what looked like a single column under the first
Tentmaster. This CSS rule predates today's session (from D031/D033) and affected the flow diagram
too (`flow_diagram.html`'s data cells also carry `class="lane-cell"`) — it likely wasn't
catastrophically visible before because earlier board/flow versions had fewer `lane-cell` columns
and shorter cell content; D038's rebuild made every data column (four Tentmasters plus a dynamic
number of Unassigned columns) use this class with taller multi-line content, which is what made
the breakage impossible to miss. This was never caught during this session's own verification
because that verification was entirely `curl` + HTML-structure parsing — accurate for confirming
the server renders correct markup, but blind to a browser-only CSS layout bug. No headless browser
was available in this environment to catch it directly.

**Consequences:**

- Fixes `/planning` and `/planning/flow` simultaneously (shared CSS class).
- No template or Python change — CSS-only, takes effect immediately (static files aren't
  process-cached).
- Not independently visually verified by me (no browser/screenshot tool available in this
  environment) — verified structurally (the underlying HTML was already confirmed correct via
  `curl` before this fix; the fix removes the one CSS rule capable of producing exactly the
  reported symptom) but needs the owner's visual confirmation.

---

## D042 — Season board: hide the Build/Up card on its own handover day

**Status:** Accepted  
**Decision:** On the day a tent's Up phase starts, its Build phase's card is no longer shown in
the same column — only the Up card, whose own detail line already reads `UP HH:MM (label)`.
Symmetrically, on the day the Break phase starts, the Up card is no longer shown in the same
column — only the Break card, whose detail line now reads `BREAK HH:MM (label)` (renamed from
`DOWN`, to match the phase-type vocabulary already shown in the block's own label). Scoped to
"same column, same job": if Build and Up (or Up and Break) end up assigned to *different*
Tentmasters, both still get their own card — suppression only removes a card that's genuinely
redundant with another one already showing in the same place.

**Rationale:** Direct owner feedback: on a handover day, the earlier phase's card added no
information the later phase's own card didn't already carry, just clutter.

**Consequences:**

- `BoardService.build()` groups each day's phases by `(column, job_id)` before building blocks,
  so a Build phase is skipped when an Up phase for the same job exists in the same column that
  day, and likewise Up is skipped when Break exists — implemented as a pre-pass over
  `day_phases` building a `phase_types_by_group` lookup, not a change to what triggers a
  card in the first place.
- Two new tests in `tests/test_board_conflicts.py` cover both the common case (Build+Up on the
  same Tentmaster, same column → Build hidden) and the edge case (Build and Up on different
  Tentmasters → both still shown, since a Tentmaster whose crew is genuinely on Build that day
  still needs their own card even if the tent's Up phase started somewhere else).
- Verified against the real reseeded `instance/kayam.db` data (SOLIDAYS' Build→Up handover on
  2026-06-17 and Up→Break handover on 2026-07-01, both currently unassigned) — confirmed live via
  the running server that the earlier card disappears and the later card's detail line reads
  correctly, while SOLIDAYS-2 (a separate job sharing the same venue, on its own independent
  schedule) is unaffected on those same days.
- 105/105 tests pass, ruff/mypy clean.

---

## D043 — Season board UI: full-bleed layout, continuous multi-day bars, explicit Unassigned columns

**Status:** Accepted  
**Decision:** Rebuild the season board presentation (template + CSS; small `BoardBlock.phase_type`
addition) so unassigned jobs, multi-day phases, and a full year are actually scannable:

1. **Full-bleed page** — planning board (and flow diagram) use `container-fluid` via a new
   `main_class` Jinja block on `base.html`, instead of Bootstrap's narrow `container`.
2. **Explicit Unassigned columns** — header shows `U1…Un` with a gold rule separating them from
   Tentmaster lanes (`ua-first`); each body cell has `data-ua-column` and empty
   `data-tentmaster-id` so drag-drop and layout cannot collapse Unassigned into the first
   Tentmaster column. (Data packing was already correct; the old visual collapse was layout/CSS.)
3. **Continuous multi-day bars** — label/subtitle only on `start`/`solo` segments; `mid`/`end` are
   colour fill only (plus `title` + visually-hidden text). Phase colours: build green, up blue,
   break amber. Default zoom is **compact**.
4. **Table layout only** — fixed column widths via `<colgroup>`, `table-layout: fixed`, no
   `display:flex` on `<td>` (reinforces D041). Sticky date column + sticky header; weekend tint on
   the date cell only.

**Rationale:** Owner feedback and screenshot showed every unassigned job appearing under Jesse and
multi-day work as repeated daily cards — unusable as a season view. Backend placement was already
correct; the board needed Excel-like density and trustworthy columns before manual planning or
auto-loads.

**Consequences:**

- `BoardBlock.phase_type` added for CSS phase classes.
- New HTML regression tests: unassigned blocks only in empty-`data-tentmaster-id` cells; visible
  `block-label` only once per multi-day phase.
- Verified against live `instance/kayam.db` (SOLIDAYS/ROSKILDE in U* cells only; 107 tests pass).

---

## D044 — Season load & crew-move generator (V1)

**Status:** Accepted  
**Decision:** Ship a planner-triggered whole-season generator (`SeasonPlanService`) rather than
waiting for the full Loads Diagram UI or a global optimiser. Button on `/loads`: **Generate season
loads & crew moves**.

**Behaviour (V1):**
- Clears only unlocked auto-generated equipment movements (`source=GENERATED`) and auto crew moves
  (notes marker); locked plans are preserved.
- Covers **section + pole** shortfalls per job (linked kit expanded on the load sheet only).
- Prefer job→job reuse of stock after contract Down; else Yard → job.
- **Leave-at-break:** job→job departs shortly after the donor’s contract Down (not just-in-time for
  the next Build). Kit must not sit on an empty site for weeks. Early arrival at the next site is
  fine; if the truck cannot make the destination’s first Build day, that donor is skipped and the
  shortfall is filled from the Yard.
- **Return to Yard:** any free stock still sitting at a site after the last job that used it is
  packed into site → Yard loads (same leave-at-break timing). Season ends with kit back at the Yard.
- Yard → job arrivals aim at the **first Build day**.
- Pack Flat (preferred) / Curtain by loading points; one load = one lorry = one `L{n}` number.
- Crew moves between consecutive Tentmaster job visits at different sites.
- Travel: haversine estimate.

**Loads Diagram (continuous overlays):**
- One absolute-positioned job rectangle per gig spanning Build→Break (not per-day cards).
- Arrivals near the top of the day row; departures near the bottom; Yard out/in markers in the
  Yard column. SVG arrows share the same coordinate system as the overlays (including header
  offset) so L# labels sit on the correct dates.
- Early arrivals and late (legacy just-in-time) departures clamp onto the first/last day of the
  related job block so every load has a visible origin and destination on the diagram.
- Click L# / load line for full From/To/dates/vehicle/haulier/contents panel.

**Not in V1:** spare-capacity hitchhiking, named asset assignment, multi-leg via-yard optimisation,
road-network distances (haversine only).

**Rationale:** Owner asked to “have a go” at season generate after board/capacity work; design
in `LOAD_ENGINE_DESIGN.md` allows an explicit auto-loads action without solving every open
algorithm question first. Continuous blocks match the Excel reference sheet the team plans from.
