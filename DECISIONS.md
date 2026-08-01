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

## D023 — Store Tentmaster membership as inclusive calendar dates

**Status:** Accepted pending Q036  
**Decision:** Tentmaster memberships use calendar dates with inclusive start and end boundaries.
Open-ended memberships are permitted, and a crew member cannot belong to overlapping Tentmasters.

**Rationale:**

- Matches the specification’s date-based membership requirement.
- Uses the safest conflict-preventing interpretation until same-day handover rules are confirmed.

**Consequences:**

- Ending one membership and starting another on the same date is currently considered an overlap.
- A future timestamp or half-open interval migration may be required if Q036 permits same-day
  handovers.

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
