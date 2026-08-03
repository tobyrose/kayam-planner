# Kayam Seasonal Planning System
## V1 Product, Functional and Technical Specification for Codex

**Document status:** Initial build specification  
**Intended implementation tool:** Codex in VS Code  
**Reference workbook:** `DAILY V8.xlsx`  
**Primary users:** Kayam tent-hire planners and operational staff  
**Initial deployment:** Local desktop-hosted web application  
**Future deployment:** Centrally hosted multi-user web application

---

# 1. Purpose of this document

This document gives Codex the context and requirements needed to build the first usable version of a seasonal scheduling and logistics application for Kayam, a large modular tent-hire company.

Codex has no access to the planning discussion that produced this document. Treat this document as the primary source of truth for V1.

The application is not merely a booking diary, asset register or haulage list. It is a time-and-space planning system coordinating:

- Events and customer contracts
- Modular tent requirements
- Individually identified tent sections and related equipment
- Tentmaster teams and individual crew members
- Crew work and crew movements
- Equipment loads and haulage
- Lorries, lorry capacity and hauliers
- Crew vans
- The Oxford yard and other operational locations
- Estimated and actual costs
- Provisional enquiries and confirmed work
- Feasibility warnings based on time, location and availability

The existing business process is represented by a very wide Excel workbook with dates running vertically. The left side shows crew activity and the right side shows equipment and lorry movements. The application must preserve that continuous seasonal-flow perspective while replacing spreadsheet conventions, hidden comments and colour-only meaning with structured data.

---

# 2. Product vision

Build a system in which a planner can:

1. Define the company’s assets, teams, locations, vehicles and cost assumptions.
2. Add an enquiry or confirmed event with contract and operational dates.
3. Specify the tents required at that event.
4. View the event on a year-long crew planning board.
5. Assign or provisionally hold physical tent sections and equipment.
6. Create and manage loads between locations.
7. See where every important equipment asset is expected to be on any date.
8. See where each Tentmaster, crew member and van is expected to be.
9. Receive warnings where equipment, crew or transport cannot reach the required place in time.
10. Estimate labour, travel and transport costs.
11. Record actual haulage cost after invoices arrive.
12. View the entire season as a continuous flow of people, equipment and transport.

The first version should provide structured planning, validation and assisted decision-making. It must not attempt to solve the entire seasonal optimisation problem automatically.

---

# 3. Existing workbook and planning model

The reference workbook uses:

- Dates vertically down the sheet
- Columns A–M for crew and Tentmaster planning
- Columns N–AS/AQ for equipment and lorry planning
- Colours to associate movements or destinations
- Load numbers such as `LD 10`, `LD 11`
- Crew movement numbers such as `CM16`
- Pale-blue areas representing the Oxford yard
- Cell comments containing named crew behind visible crew totals
- Repeated labels such as `BUILD`, `BREAK`, loading, unloading and travel
- Contract milestone notation such as `UP 29/5 @ 20:00`
- Asset codes such as `K1`, `M21`, `P2`, `ct1`, `sb1`

The workbook is successful because it acts as a visual proof that the season works. Users can scan across a date and answer:

- Where are the crews?
- What are they doing?
- Where is each section?
- Which loads are moving?
- What is at Oxford?
- Which job is each asset supporting?
- Can the next event happen?

The application must retain that high-density, continuous visual planning capability.

---

# 4. Core business concepts

## 4.1 Modular tents

**Updated 2026-08-02 (D030):** A tent is not booked by a named size template (e.g. "10-pole").
Named pole-count templates cannot faithfully represent what is actually booked, because many
different section combinations produce the same pole count (e.g. a run of 8 poles could come from
several different end/middle combinations). A tent is instead a sequence of section codes,
matching exactly how the business already writes it — e.g. `K-M-M-M-K` (2 Kayam ends, 3 20m
middles). Poles are never entered directly: they are derived from the sequence length via a
per-family formula (Kayam's confirmed formula is `poles = sections × 2 − 2`), and the derived pole
quantity is itself shown as a normal requirement (poles are a "big item" too, just not one a
planner types in).

Only the visible/big items (ends, middles, triangles, covers, and the derived poles) are shown on
the primary requirement/loading view. Each of those can additionally imply further hidden
equipment — configurable per equipment type as a linked bill of materials (e.g. a 20m middle
implies bale rings and side poles; a pole pair implies side guys and Tifors) — which is never
entered directly and only shown in a detailed view, not the main loading list.

A tent requirement is not itself a physical tent asset. It is a requirement fulfilled by assigning named physical assets.

Example:

```text
Requirement:
1 × K-M-M-M-K (Kayam)

Derived:
2 Kayam ends
3 compatible middles
4 pole pairs (5 sections × 2 − 2 = 8 physical poles ÷ 2 per pair)
Linked equipment (hidden): bale rings, side guys, Tifors, ...
```

Possible physical assignment:

```text
Ends: K1, K2
Middles: M3, M7, M9
Poles: P21–P24
```

## 4.2 Individually tracked equipment

Important equipment is individually named and must be tracked through the season.

Examples seen in the workbook include:

- Kayam ends
- Siam ends
- 20 m middles
- 15 m middles
- Stage covers
- Triangles or hex equipment
- Valhalla ends
- Poles
- Anchors
- Crew tents
- Stake bashers
- Rock drills
- Auger equipment
- Other ancillary and metal equipment

Examples of codes:

```text
K1, K2, K3
M21, M24, M25
m5, m6, m7
SC1, SC2
P2–P21
T1, T2
a1–a6
ct1–ct5
sb1–sb4
rd1–rd3
VA1, VS1, V1–V5
```

The asset model must be configurable. It must not assume every item is an end, middle or pole.

Some equipment will be individually tracked. Some may be quantity-tracked. V1 must support both.

## 4.3 Tentmasters and crew

**Updated 2026-08-02 (resolves Q001):** A Tentmaster is a named individual who leads a crew, not
an abstract team — confirmed directly by `reference/LOADS 26 V8.xlsx`'s `TM DETAILS` sheet
(Martin Peers, Ross Markham, Jesse Thompson, Marley Yuill, each with initials, phone and email
used throughout the reference data). "The Tentmaster's crew" is whoever currently belongs to
their team via `TentmasterMembership`.

The reference workbook includes four main Tentmaster lanes:

- Max/Martin
- Ross
- Jesse
- Marley

Crew members are individuals.

Crew members can join and leave Tentmasters over time, so team membership must be date-based
rather than a permanent foreign key. Membership dates are half-open (`end_at` is the first day no
longer active, exclusive), so a crew member can end with one Tentmaster and start with another on
the same calendar date — see D023/D029 and resolved Q036.

A job phase is assigned a Tentmaster, not individual crew. Headcount and named crew are **derived**
from whoever is an active `TentmasterMembership` member of that Tentmaster during the phase's
dates (excluding anyone with an overlapping unavailable-type `CrewAvailability` row) — a planner
does not re-enter names per phase. There is no per-person override mechanism; a job's local/hired
crew is booked separately as anonymous headcount over a job-level date range (`LocalCrewBooking` —
see 7.22), not as named exceptions to the derived roster (D036).

V1 must support:

- Automatically derived crew presence per phase, from Tentmaster membership
- Required headcount before names are known
- Local/hired crew booked as anonymous headcount over a job-level date range
- People moving between Tentmasters, including same-day, managed on a roster-over-time view
- Crew starting and finishing
- Crew availability and leave
- Daily crew totals, per Tentmaster and in total
- Hourly labour cost
- Travel cost

## 4.4 Jobs, events and locations

A location is a reusable physical place:

- Festival site
- Customer site
- Yard
- Depot
- Workshop
- Airport
- Ferry port

A job is a commercial and operational event at a location.

A single location may host several jobs over time.

A job may include several tents and several work phases.

## 4.5 Loads and equipment movement

A load is a planned movement of equipment between locations.

Example:

```text
Load 14
Origin: Oxford Yard
Destination: Roskilde
Departure: 7 June 18:00
Expected arrival: 8 June 16:00
Vehicle type: Standard artic
Contents: K1, K2, M1, M2, P11–P16, Anchor Kit A3
```

A single movement between sites may require several loads.

Model:

```text
Transport movement
└── One or more loads
    └── Equipment items
```

A load may exist before every detail is known.

Suggested statuses:

- Required
- Proposed
- Numbered
- Contents assigned
- Sent to haulier
- Booked
- Loading
- Departed
- Arrived
- Unloaded
- Invoiced
- Closed
- Cancelled

## 4.6 Crew moves

Crew travel must be planned separately from equipment loads.

Crew movement may involve:

- Van
- Ferry
- Flight
- Train
- Taxi
- Hire vehicle
- Multiple journey legs

Model:

```text
Crew movement plan
└── One or more journey legs
    └── Named passengers
```

Crew movements should have identifiers such as `CM16`.

## 4.7 Oxford yard

The Oxford yard is a major planning node used for:

- Storage
- Returns
- Loading
- Unloading
- Consolidation
- Staging
- Inspection
- Maintenance

Represent it as a normal location with type `yard`. Do not hard-code Oxford-specific logic.

## 4.8 Time-aware and space-aware availability

The system must answer:

> Is a compatible asset available, and can it physically reach the next required location before it is needed?

An asset may be:

- At yard
- At site
- Building
- In use
- Waiting
- Striking
- In transit
- Under maintenance
- Unavailable

A journey may be direct or multi-leg.

Example:

```text
Roskilde → Oxford → Scotland
```

V1 must support multi-leg plans, but it is not required to discover the globally optimal route automatically.

---

# 5. V1 scope

## 5.1 V1 must include

### Administration

- Locations
- Coordinates and geocoding
- Tent families
- Tent configurations
- Equipment types
- Equipment assets
- Tentmasters
- Crew members
- Date-based Tentmaster membership
- Crew availability
- Lorry types and capacities
- Optional specific lorry records
- Vans
- Hauliers
- Cost assumptions and rate cards
- Build and strike defaults
- Scheduling settings

### Planning

- Create, edit, copy and cancel jobs
- Create a job by dragging across dates in a crew lane
- Support enquiry, quoted, provisional and confirmed jobs
- Record contract and operational dates
- Add one or more tent requirements
- Generate component requirements
- Create build, show, maintenance and strike phases
- Assign Tentmasters
- Assign named crew and provisional headcount
- Assign physical equipment assets
- Create movements and numbered loads
- Assign equipment to loads
- Validate lorry capacity
- Create crew movements and journey legs
- Assign vans and passengers
- Display daily crew totals
- Display asset location and movement through the season
- Display provisional and confirmed work differently
- Detect scheduling conflicts
- Estimate labour and transport cost
- Record actual load cost and invoice reference
- Export loads and crew-moves lists

### Distance awareness

- Geocode locations
- Store latitude and longitude
- Calculate road distance and estimated HGV time through a provider abstraction
- Cache results
- Allow manual override
- Show feasibility warnings

### Planner control

- Preserve manual locks
- Distinguish suggestions from approved assignments
- Warn before destructive changes
- Basic audit history

## 5.2 Outside V1

Do not implement these as V1 requirements:

- Full automatic whole-season optimisation
- Global automatic multi-leg hitchhiking optimisation
- Payroll
- Accounting-system integration
- Invoice OCR
- Live GPS
- Driver tachograph compliance
- Real-time traffic
- Automatic ferry or flight booking
- Customer portal
- Haulier portal
- Native mobile apps
- Complex enterprise permissions
- Professional driver navigation

The architecture should leave room for these later.

---

# 6. Recommended architecture

## 6.1 Stack

Use:

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- SQLite initially
- Jinja2
- HTMX
- Vanilla JavaScript for planning-board interaction
- Bootstrap 5 or similarly lightweight CSS
- Pydantic settings
- pytest
- OpenRouteService behind a provider interface

Avoid React in V1 unless a specific board interaction cannot reasonably be implemented without it.

Run locally with:

```bash
uvicorn app.main:app --reload
```

or:

```bash
python run.py
```

Default URL:

```text
http://127.0.0.1:8000
```

## 6.2 Future portability

Use SQLAlchemy constructs compatible with SQLite and PostgreSQL/MySQL.

Do not scatter SQLite-specific SQL throughout the code.

Use timezone-aware timestamps.

Store a location timezone for cross-border work.

## 6.3 Suggested project layout

```text
kayam-planner/
├── AGENTS.md
├── README.md
├── SPECIFICATION.md
├── DECISIONS.md
├── OPEN_QUESTIONS.md
├── pyproject.toml
├── alembic.ini
├── .env.example
├── run.py
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   ├── routes/
│   ├── templates/
│   ├── static/
│   ├── integrations/
│   │   └── routing/
│   └── domain/
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── scripts/
└── reference/
    └── DAILY V8.xlsx
```

## 6.4 Layering rules

- Routes handle HTTP and request validation.
- Services contain business rules.
- Repositories contain database access.
- Domain modules contain scheduling and feasibility logic.
- Templates contain display logic only.
- JavaScript must not become the source of truth.
- Routing must be hidden behind a provider interface.
- Cost calculations must be testable Python services.

---

# 7. Core data model

The exact table names may differ, but these concepts are required.

## 7.1 User

Fields:

- id
- username
- display_name
- email
- is_admin
- is_active
- created_at
- updated_at

V1 may support local no-login development mode, but the model should exist.

## 7.2 Location

Fields:

- id
- name
- location_type
- address_line_1
- address_line_2
- city
- region
- postcode
- country_code
- latitude
- longitude
- timezone
- geocoding_provider
- geocoding_place_id
- geocoded_at
- access_notes
- hgv_notes
- receiving_notes
- default_unload_duration_minutes
- active
- created_at
- updated_at

Location types:

- site
- yard
- depot
- workshop
- airport
- ferry_port
- other

Requirements:

- Oxford yard should be seedable as a normal yard.
- Coordinates may be provider-resolved or manual.
- Ambiguous geocoding must require confirmation.

## 7.3 TentFamily

Fields:

- id
- name
- description
- active

Examples:

- Kayam
- Siam
- Valhalla

## 7.4 EquipmentType

**Updated 2026-08-03 (D030, D037):** `code` is the real business letter/token vocabulary (K, M, m,
s, T, SC, V, VOE, VNE, P, X, plus non-sequence types AD/SB/VB/RD/CT and linked-only types like
BALE_RING) — case-sensitive by design, since M (20m middle) and m (15m middle), and K (Kayam End)
and s (Siam End), are genuinely different types. `category` distinguishes "section" (bookable in a
job's sequence), "pole" (derived from section count, never typed directly), "linked" (implied via
`EquipmentLink`, never typed directly), and "ancillary" (tracked independently of any tent
sequence).

Fields:

- id
- code
- name
- category
- tent_family_id nullable
- tracking_mode: individual or quantity
- pack_size — physical units per tracked asset (e.g. 2 for a pole type tracked as a pair)
- section_capacity_units
- pole_capacity_units
- ancillary_capacity_units
- weight_kg
- default_build_stage
- maintenance_interval_days nullable
- active
- notes

## 7.5 EquipmentAsset

Fields:

- id
- asset_code
- equipment_type_id
- variant
- generation
- initial_location_id
- current_status
- serviceable
- commissioned_date
- retired_date
- replacement_value
- notes
- active
- created_at
- updated_at

Rules:

- `asset_code` must be unique.
- Do not rely on a manually edited current location as the only source of truth.
- Predicted location should be derived from assignments and movements.

## 7.6 InventoryBalance

For quantity-tracked equipment.

Fields:

- id
- equipment_type_id
- location_id
- quantity
- effective_at
- source_reference
- notes

## 7.7 TentFamily

**Updated 2026-08-02 (D030):** replaces the removed `TentConfiguration` named-template model.
Named pole-count sizes ("Kayam 10-pole") are gone; a family instead owns the formula that derives
poles from a booked section sequence, plus the build/strike/crew defaults that used to live per
named size.

Fields:

- id
- name
- description nullable
- pole_equipment_type_id nullable — which EquipmentType fulfils this family's derived pole
  requirement (e.g. the Kayam King Pole pair). No poles are derived while null.
- pole_count_multiplier — default 2
- pole_count_offset — default -2 (Kayam's confirmed formula: `poles = sections × 2 − 2`)
- default_build_hours
- default_strike_hours
- minimum_crew
- preferred_crew
- active

## 7.8 EquipmentLink

**Updated 2026-08-02 (D030):** replaces the removed `TentConfigurationRequirement` flat BOM. A
self-referential, admin-editable cascade: booking one equipment type implies a quantity of
another, recursively (a child may itself be a parent of further links). Never entered directly by
a planner and never shown on the main loading list — only in a load's detailed view.

Fields:

- id
- parent_equipment_type_id
- child_equipment_type_id
- quantity_per_parent
- notes nullable

A parent cannot link to itself; expansion additionally guards against indirect cycles at
requirement-generation time.

## 7.9 Tentmaster

Fields:

- id
- name
- lead_crew_member_id nullable
- home_location_id nullable
- default_van_id nullable
- active
- notes

## 7.10 CrewMember

Fields:

- id
- name
- role
- employment_type
- hourly_cost
- overtime_hourly_cost
- travel_hourly_cost
- daily_allowance
- can_drive_van
- can_drive_hgv
- skills
- home_location_id nullable
- active
- notes

## 7.11 TentmasterMembership

Fields:

- id
- tentmaster_id
- crew_member_id
- start_at
- end_at nullable — half-open: the first date no longer active. Open-ended when null. A crew
  member may end one membership and start another on the same date (resolved Q036).
- is_default
- notes

Prevent overlapping active memberships unless explicitly allowed.

## 7.12 CrewAvailability

Fields:

- id
- crew_member_id
- start_at
- end_at
- status
- notes

Statuses:

- unavailable
- leave
- training
- restricted
- available_override

## 7.13 LorryType

Fields:

- id
- name
- section_capacity_units
- pole_capacity_units
- ancillary_capacity_units
- payload_kg
- passenger_capacity
- default_cost_per_km
- minimum_load_cost
- notes
- active

Do not reduce capacity to one scalar.

## 7.14 Lorry

Fields:

- id
- registration_or_name
- lorry_type_id
- haulier_id nullable
- ownership_type
- home_location_id nullable
- active
- notes

Ownership types:

- owned
- hired
- supplier

## 7.15 Van

Fields:

- id
- registration_or_name
- passenger_capacity
- cargo_capacity_units
- home_location_id
- ownership_type
- cost_per_km
- active
- notes

## 7.16 Haulier

Fields:

- id
- name
- contact_name
- email
- phone
- currency
- default_cost_per_km
- minimum_load_cost
- waiting_hourly_cost
- fuel_surcharge_percent
- active
- notes

## 7.17 Job

**Updated 2026-08-03 (D036):** Contract Up/Down dates moved off `Job` entirely — a job with
multiple tents can have different contract dates per tent, so they now live on
`JobTentRequirement.contracted_up_at`/`contracted_down_at` (7.18). `site_access_at` (now nullable)
and `site_clear_by` are the only dates that genuinely apply to the whole job.

Fields:

- id
- job_code
- name
- customer_name
- location_id
- commercial_status
- planning_status
- confidence_percent nullable
- contract_revenue
- currency
- site_access_at nullable
- site_clear_by nullable
- maintenance_cover_required
- catering_arrangement
- accommodation_arrangement
- ground_type
- local_crew_supplied
- local_crew_required
- build_scope
- strike_scope
- operational_notes
- commercial_notes
- deposit_received_at nullable
- confirmed_at nullable
- cancelled_at nullable
- created_at
- updated_at

Commercial statuses:

- enquiry
- quote_in_preparation
- quoted
- deposit_requested
- deposit_received
- confirmed
- cancelled
- completed

Planning statuses:

- not_planned
- provisional_plan
- feasible
- at_risk
- conflict
- planner_approved
- operationally_locked

Rules:

- Confirming a job must not silently replace existing confirmed assignments.
- Provisional jobs may create soft holds.
- Confirmed jobs may create hard allocations after approval.
- Validate chronological date order.

## 7.18 JobTentRequirement

**Updated 2026-08-02/03 (D030, D036):** `tent_configuration_id` is removed. The booked tent is
instead an ordered sequence of section codes, held in the related `JobTentSection` rows (7.18a) —
e.g. K-M-M-M-K. `contracted_up_at`/`contracted_down_at` are this tent's fixed contract dates, set
once when the tent is added (`contracted_down_at > contracted_up_at` enforced by a DB constraint);
the old per-tent override fields (build start/duration, strike duration, required crew) are gone —
the schedulable unit is now this tent's own `UP` `JobPhase` (7.21), freely reassignable within this
window.

Fields:

- id
- job_id
- quantity
- custom_name
- contracted_up_at
- contracted_down_at
- notes

## 7.18a JobTentSection

One position in a `JobTentRequirement`'s section sequence.

Fields:

- id
- job_tent_requirement_id
- sequence_index
- equipment_type_id — must be a `category == "section"` EquipmentType

## 7.19 JobEquipmentRequirement

Fields:

- id
- job_id
- job_tent_requirement_id nullable
- equipment_type_id
- quantity_required
- required_on_site_at
- releasable_at
- required_stage
- source
- status
- notes

Sources:

- generated
- manual

Statuses:

- unresolved
- partially_assigned
- assigned
- conflict

Regeneration must preserve manual exceptions unless the user explicitly approves their removal.

## 7.20 EquipmentAssignment

Fields:

- id
- job_equipment_requirement_id
- equipment_asset_id
- start_at
- end_at
- allocation_strength
- assignment_source
- locked
- status
- notes

Allocation strengths:

- soft
- hard

Sources:

- suggested
- manual

Rules:

- Prevent hard overlapping assignments.
- Soft overlap creates a warning.
- Locked assignments survive recalculation.
- Asset must be compatible.

## 7.21 JobPhase

**Updated 2026-08-03 (D036):** Phase types simplified to Build/Up/Break (`other` kept as a
manual-only escape hatch); the old site_prep/handover/show/maintenance/strike/clear_site set is
gone. `job_tent_requirement_id` ties an `up` phase to the specific tent it's for — a `CheckConstraint`
enforces it's set if and only if `phase_type = 'up'`. `build`/`break` stay job-level
(`job_tent_requirement_id` null) since the same crew typically builds/strikes every tent on a job
together. An `up` phase's dates must fall within its tent's `contracted_up_at`/`contracted_down_at`
window (validated in `JobService`); a tent's Up window can be freely split across several Up
phases/Tentmasters (a crew handover mid-contract) via `add_phase()`/`delete_phase()` — phases are
no longer auto-generated and continuously re-synced, only seeded once when a tent is added.

Fields:

- id
- job_id
- job_tent_requirement_id nullable — set if and only if phase_type is `up`
- phase_type
- tentmaster_id nullable
- start_at
- end_at
- required_headcount
- notes
- locked
- source

Phase types:

- build
- up
- break
- other

## 7.22 LocalCrewBooking

**Updated 2026-08-03 (D036):** Replaces the old `CrewAssignment` ADD/EXCLUDE/placeholder override
mechanism, which is deleted entirely. Local/hired crew is anonymous headcount only — no names, no
per-person exceptions to the Tentmaster-derived roster (7.11, 4.3). A booking is job-level and
date-ranged, not tied to a specific phase; it joins whichever phase(s) are active during its
window (`roster.phase_roster()`), so moving or adjusting phases never requires re-entering local
crew.

Fields:

- id
- job_id
- headcount
- start_at
- end_at
- notes

`end_at > start_at` and `headcount > 0` are enforced by DB constraints.

## 7.23 EquipmentMovement

Fields:

- id
- movement_code
- origin_location_id
- destination_location_id
- earliest_departure_at
- required_arrival_at
- planned_departure_at nullable
- planned_arrival_at nullable
- status
- movement_source
- locked
- route_distance_km nullable
- route_drive_minutes nullable
- operational_duration_minutes nullable
- notes

Movement sources:

- required
- suggested
- manual

## 7.24 Load

Fields:

- id
- load_number
- equipment_movement_id
- lorry_type_id nullable
- lorry_id nullable
- haulier_id nullable
- planned_departure_at
- planned_arrival_at
- actual_departure_at nullable
- actual_arrival_at nullable
- status
- estimated_haulage_cost
- estimated_ferry_cost
- estimated_toll_cost
- estimated_other_cost
- actual_haulage_cost
- actual_ferry_cost
- actual_toll_cost
- actual_waiting_cost
- actual_other_cost
- currency
- invoice_reference nullable
- sent_to_haulier_at nullable
- locked
- notes

Load number must be unique within the chosen season-numbering scheme.

## 7.25 LoadItem

Fields:

- id
- load_id
- equipment_asset_id nullable
- equipment_type_id nullable
- quantity
- load_sequence nullable
- notes

Support individual and quantity-based equipment.

## 7.26 CrewMovement

Fields:

- id
- movement_code
- origin_location_id
- destination_location_id
- planned_departure_at
- planned_arrival_at
- purpose
- status
- estimated_cost
- actual_cost
- currency
- notes
- locked

## 7.27 CrewJourneyLeg

Fields:

- id
- crew_movement_id
- sequence
- mode
- origin_location_id nullable
- destination_location_id nullable
- carrier
- reference_number
- departure_at
- arrival_at
- van_id nullable
- estimated_cost
- actual_cost
- notes

Modes:

- van
- flight
- ferry
- train
- taxi
- hire_vehicle
- other

## 7.28 CrewMovementPassenger

Not affected by the D036 crew-model rework — unrelated to job-phase assignment.

Fields:

- id
- crew_movement_id
- crew_member_id nullable
- placeholder_label nullable
- quantity — 1 when named (crew_member_id set); may be >1 on a placeholder row
- joining_tentmaster_id nullable
- leaving_tentmaster_id nullable
- notes

Either a named person (quantity always 1) or a placeholder label (any quantity) must be present,
not both.

## 7.29 RouteCache

Fields:

- id
- origin_location_id
- destination_location_id
- routing_profile
- vehicle_profile_hash
- provider
- distance_metres
- duration_seconds
- route_summary
- calculated_at
- expires_at nullable
- manual_override
- notes

## 7.30 SupplierInvoice

Fields:

- id
- haulier_id nullable
- supplier_name
- invoice_reference
- invoice_date
- total_amount
- currency
- notes

## 7.31 LoadCostAllocation

Fields:

- id
- supplier_invoice_id
- load_id nullable
- job_id nullable
- cost_category
- amount
- notes

Supports invoices covering several loads.

## 7.32 AuditLog

Fields:

- id
- entity_type
- entity_id
- action
- changed_by_user_id nullable
- changed_at
- summary
- before_json nullable
- after_json nullable

Audit at least:

- Job dates and status
- Equipment assignments
- Loads
- Crew assignments
- Costs
- Locks

---

# 8. Scheduling rules

## 8.1 Date validation

**Updated 2026-08-03 (D036):** `must_be_up_at`/`show_start_at`/`show_end_at`/`strike_available_at`
no longer exist on `Job` — contract dates are per-tent (7.18). Validate:

```text
job_tent_requirement.contracted_down_at > job_tent_requirement.contracted_up_at  (DB constraint)
job.site_clear_by >= job.site_access_at  (DB constraint, both nullable)
up_phase.start_at/end_at within its tent's contracted_up_at/contracted_down_at  (JobService)
```

Allow unusual cases only through explicit override and warning.

## 8.2 Requirement expansion

**Updated 2026-08-02 (D030):** expansion is now recursive rather than a flat per-template lookup.
When a tent requirement (a section sequence) is added:

1. Add one unit of each section's equipment type per booked tent.
2. Derive the pole quantity from the sequence length via the family's formula, divided by the
   pole equipment type's pack size.
3. For every section and every derived pole quantity, recursively cascade through any configured
   `EquipmentLink` rows (a linked child may itself have further links), cycle-guarded.
4. Multiply everything by the tent requirement's quantity.
5. Create or update equipment requirements from the combined totals.
6. Preserve manual additions (only `GENERATED`-source rows are ever touched).
7. Calculate required-on-site time from build stage.

Example:

```text
2 × (K-M-M-K)
= 4 ends (2 K × 2 tents)
+ 4 middles (2 M × 2 tents)
+ 6 poles (per tent: 4 sections × 2 − 2 = 6 physical poles ÷ 2 per pair = 3 pairs; × 2 tents = 6)
+ cascaded linked equipment (bale rings under M, side guys/Tifors under the poles, ...)
```

## 8.3 Build stages

Support at least:

- Site preparation
- Poles and anchors
- Main sections
- Completion and ancillary gear
- Maintenance
- Strike

Equipment may arrive at different times depending on stage.

Users must be able to override required arrival times.

## 8.4 Equipment compatibility

An asset may satisfy a requirement only when:

- Type matches or is explicitly compatible.
- Asset is active and serviceable.
- It has no conflicting hard allocation.
- It can reach the job before required time.
- It is not locked into an incompatible plan.

## 8.5 Derived asset state

Derive asset state from assignments and movements where possible:

- At yard
- At site
- Allocated
- Building
- In use
- Striking
- Waiting
- In transit
- Maintenance
- Unavailable

## 8.6 Direct travel feasibility

For a proposed transition:

```text
previous release time
+ loading allowance
+ operational travel duration
+ unloading allowance
<= next required-on-site time
```

Use configurable risk thresholds.

Example:

- Green: at least 24 hours margin
- Amber: 6–24 hours
- Red: under 6 hours or impossible

## 8.7 Multi-leg movement

V1 must support manual multi-leg chains.

It should permit:

- Routing through Oxford
- Routing through another job
- Adding equipment to an existing load with capacity
- Validating each leg

V1 may suggest obvious spare-capacity opportunities, but must not silently make changes.

## 8.8 Receiving crew

A load should not arrive without an authorised receiving crew or representative.

For V1:

- Permit save with warning.
- Allow override with notes.
- Support receiving windows later.

## 8.9 Load capacity

Calculate:

- Section units used
- Pole units used
- Ancillary units used
- Weight used

Statuses:

- Within capacity
- Near capacity
- Over capacity
- Capacity unknown

Use configurable thresholds.

## 8.10 Crew conflicts

**Updated 2026-08-03 (D036):** There is no per-person assignment row to check for overlap anymore
— crew presence is derived from Tentmaster membership. The equivalent checks are: a Tentmaster
double-booked across two overlapping phases (implemented), and a phase's derived+booked headcount
falling short of `required_headcount` (implemented). An unavailable crew member is reflected as a
greyed-out roster display (D035) rather than a standalone conflict warning.

Warn when:

- A Tentmaster is double-booked between overlapping phases.
- Required headcount is not met (derived roster + local crew bookings, short of required).
- Travel between assignments is infeasible.
- A van is over passenger capacity.
- A crew movement arrives after work begins.

## 8.11 Hard versus conditional conflict

### Hard conflict

- Two confirmed jobs need the same hard-assigned asset.
- One person is assigned to overlapping confirmed work.
- A load exceeds known capacity.
- A confirmed asset cannot reach the next job.

### Conditional conflict

- A provisional job competes with confirmed work.
- Two provisional jobs rely on the same equipment.
- Timing margin is low.
- Lorry or crew is still unassigned.

## 8.12 Locks

Every major assignment and movement should support `locked`.

Automatic recalculation must preserve locked values.

If a new change makes a locked plan impossible, report the conflict instead of replacing the plan.

## 8.13 Suggested versus committed

Automatically created ideas must be marked as suggested.

Planner approval is required before they become committed.

---

# 9. Cost model

## 9.1 Job revenue

Store contract revenue on the job.

Use `contract revenue`, not ambiguous `contract cost`.

## 9.2 Estimated transport cost

Possible calculation:

```text
minimum load cost
+ road distance × cost per km
+ ferry estimate
+ toll estimate
+ overnight allowance
+ manual extras
```

Allow manual override.

Store estimate source:

- Manual
- Haulier rate card
- Standard route price
- Distance formula

## 9.3 Actual transport cost

Support:

- Invoice reference
- Haulage
- Ferry
- Toll
- Waiting
- Other
- Total actual
- Variance from estimate

Support one invoice covering several loads.

## 9.4 Crew cost

Estimate from:

- Planned work hours
- Hourly rate
- Overtime rate
- Travel hours
- Travel rate
- Daily allowance
- Manual adjustments

Do not implement payroll.

## 9.5 Job margin

Calculate:

```text
Estimated margin =
contract revenue
- estimated haulage
- estimated labour
- estimated crew travel
- estimated ferries/flights
- estimated other costs
```

Also calculate actual margin when actuals exist.

Do not distribute shared costs automatically without an explicit rule.

---

# 10. Routing integration

## 10.1 Provider abstraction

Create an interface similar to:

```python
class RoutingProvider(Protocol):
    def geocode(self, query: str) -> list[GeocodingResult]:
        ...

    def route(
        self,
        origin: Coordinates,
        destination: Coordinates,
        vehicle_profile: VehicleProfile,
    ) -> RouteResult:
        ...
```

Initial provider:

- OpenRouteService
- HGV profile where available

Also implement manual/fallback routing.

## 10.2 Configuration

Environment variables:

```text
ROUTING_PROVIDER=openrouteservice
OPENROUTESERVICE_API_KEY=
DATABASE_URL=sqlite:///./instance/kayam.db
SECRET_KEY=
APP_ENV=development
DEFAULT_TIMEZONE=Europe/London
```

## 10.3 Geocoding

- Geocode when a location is created or changed.
- Show resolved address and coordinates.
- Require confirmation where ambiguous.
- Cache result.
- Permit manual coordinates.

## 10.4 Route caching

Cache by:

- Origin
- Destination
- Vehicle profile
- Provider

Do not call the API every time the board loads.

## 10.5 Operational journey duration

Keep separate:

- API driving duration
- Break/rest allowance
- Ferry/check-in allowance
- Border allowance
- Contingency
- Total operational duration

Use a simple configurable planning formula in V1.

State clearly that it is planning support, not professional driver navigation.

---

# 11. User interface requirements

## 11.1 General principles

Preserve high information density.

Do not replace the workbook with oversized cards.

Required:

- Compact rows
- Sticky date column
- Sticky headers
- Year, month and week zoom
- Full-season overview
- Expandable details
- Search and highlight
- Filters
- Side-panel editing
- Provisional versus confirmed styling
- Colour plus text or pattern
- Synchronized crew and equipment views

## 11.2 Main navigation

Suggested:

- Planning Board
- Jobs
- Loads
- Crew Moves
- Equipment
- Crew
- Locations
- Vehicles
- Costs
- Conflicts
- Admin
- Reports

## 11.3 Season board and flow diagram

**Updated 2026-08-03 (D031, D032, D033; rebuilt again per D038):** The single combined board
originally envisioned below shipped as **two separate pages** instead, both dates-down-the-side/
one-row-per-day like the reference workbook, sharing the same block/segment CSS so a job reads
identically on both:

- **`/planning` (season board)** — one column per Tentmaster (a multi-day phase/activity renders
  as one contiguous bar per column, not a repeated per-day flag), plus a dynamic number of
  "Unassigned / quoted" columns (interval-packed: a job keeps the same column for the whole span
  of its currently-unassigned phases, using as few concurrent columns as the range actually
  needs — not a single flat lane). The separate "Milestones" and "Equipment" columns from the
  first rebuild are gone (D038): equipment-asset movement is now shown only on the flow diagram
  below, and everything else — contract Up/Down markers, load arrive/depart, crew-move
  references, local-crew arrive/depart — is folded into stacked lines inside the relevant
  Tentmaster/Unassigned block itself, auto-growing the block vertically rather than living in a
  side column. A job block can be dragged onto a different Tentmaster column to reassign it;
  clicking a job opens a read-only side panel showing the job's full detail (11.5); clicking the
  "+" in an empty Tentmaster cell opens a small form to add a `CrewActivity` for that Tentmaster
  over a date range. The
  standalone Crew Board (`/planning/crew`) is deleted — the season board is now the one place to
  both see and add crew activities.
- **`/planning/flow` (loads/equipment flow diagram)** — one column per location instead of
  Tentmaster; each location's column shows a block for every day a job occupies that site (job
  code + booked tent section sequence, e.g. `KMMMK`); an SVG line overlay draws each load's
  journey from its origin column/depart-date to its destination column/arrival-date.

Both pages must show asset continuity, as the original vision below required — that requirement
carried through even though the single-page layout didn't.

<details>
<summary>Original V1 vision (pre-D031/D032, superseded by the two-page shape above)</summary>

Layout:

```text
Dates vertically
Crew/Tentmaster lanes on the left
Equipment/load lanes on the right
Shared vertical scrolling
```

Show:

- One row per day at standard zoom
- Tentmaster work blocks
- Daily crew counts
- Total daily crew
- Equipment position
- Equipment movement
- Oxford yard periods
- Load numbers
- Job colours
- Contract milestones
- Warnings

</details>

## 11.4 Dragging to create work

**Updated 2026-08-03 (D033, D038):** What's actually shipped is drag-*an-existing-block* onto a
different Tentmaster column to reassign it (`POST /planning/move-phase`, D033) — not
drag-across-empty-cells to create new work, as originally envisioned below. Creating work directly
from the board shipped scoped down from the original vision: clicking the "+" in an empty cell in
a Tentmaster's column opens a small form (`GET/POST /planning/activity/new`) to create a
`CrewActivity` for that Tentmaster over a date range (reusing `create_activity()`), redirecting
back to the board's current date range on save; new jobs are still created via the Jobs page, not
the board.

<details>
<summary>Original V1 vision (broader scope than the planned chunk-5 version)</summary>

In a Tentmaster lane:

1. User drags across a date range.
2. Release opens `Add Job or Activity`.
3. Pre-fill Tentmaster and dates.
4. Allow:
   - New job
   - Existing job phase
   - Training
   - Leave
   - Yard work
   - Travel
   - Other activity

Do not paint cells. Create structured records.

</details>

## 11.5 Job editor

**Updated 2026-08-03 (D038):** The job page splits into a read view (`GET /jobs/{id}`, the
default) and a separate edit surface (`GET/POST /jobs/{id}/edit`) — reversing the earlier
inline-editable version. The read view shows every section below read-only, with a single "Edit
job" button; all add/remove/edit forms (tent requirements, phases, local crew, ancillary
equipment, equipment-assignment approval) live only on the edit page, appended after the
Commercial/Location/Dates/Operations fields shown there. `GET /jobs/{id}/summary` renders the
same read-only content as a bare fragment (no navigation chrome) for the season board's job side
panel — click a job block on `/planning` to see it without leaving the board, plus an Edit button
through to the full edit page.

Sections:

### Commercial

- Name
- Customer
- Status
- Deposit
- Revenue
- Confidence
- Notes

### Location

- Select or create location
- Geocoding preview
- Access and HGV notes

### Dates

**Updated 2026-08-03 (D036):** Contract Up/Down are per-tent now, not job-wide — moved into the
Tent requirements section below.

- Site access
- Site clear

### Tent requirements

**Updated 2026-08-03 (D030, D036):** "Tent configuration" replaced by a section sequence; contract
dates moved in from the job-wide Dates section above.

- Section sequence (e.g. `K-M-M-M-K`)
- Contract Up / Contract Down (per tent)
- Quantity
- Generated component summary

### Crew

**Updated 2026-08-03 (D036):** "Named crew" is derived from Tentmaster membership, not entered —
there's no per-person editing here. Local crew is job-level headcount, not tied to a phase. There
is no separate "maintenance crew" concept — `PhaseType.MAINTENANCE` was removed; only the
job-level `maintenance_cover_required` boolean survives.

- Tentmaster (per phase)
- Required headcount (per phase)
- Derived crew (read-only, from Tentmaster membership)
- Local/hired crew (job-level, date-ranged headcount)
- Maintenance cover required (boolean)

### Equipment

- Requirements
- Suggested assets
- Manual assignment
- Soft or hard allocation
- Locks

### Transport

- Incoming and outgoing movement
- Loads
- Route duration
- Warnings

### Cost

- Revenue
- Labour estimate
- Transport estimate
- Margin

## 11.6 Status styling

Suggested:

- Confirmed: solid fill
- Provisional/quoted: striped or lower opacity
- Cancelled: hidden by default or struck through
- Conflict: warning icon/border
- Locked: lock icon

Do not rely on colour alone.

## 11.7 Equipment interactions

Support:

- Click asset to highlight its whole season.
- Click job to highlight assigned assets.
- Click load to highlight contents.
- Click location to highlight assets there.
- Open asset timeline.
- Add asset to an existing load.
- Lock approved assignments.
- Show impossible location jumps.

## 11.8 Crew interactions

Support:

- Isolate a Tentmaster.
- Click crew count to see names (derived from Tentmaster membership).
- Move a person between Tentmasters (roster board, D029).
- Add local/hired crew headcount to a job, date-ranged, no name (`LocalCrewBooking`, D036).
- Highlight an individual’s season.
- Show shortages.
- Show van-capacity warnings.

## 11.9 Loads screen

Columns:

- Load number
- Origin
- Destination
- Departure
- Arrival
- Status
- Vehicle type
- Haulier
- Capacity used
- Estimated cost
- Actual cost
- Invoice
- Warnings

Load detail:

- Contents
- Capacity summary
- Route
- Costs
- Notes
- Timeline
- Audit history

## 11.10 Crew Moves screen

Columns:

- Crew move number
- Origin
- Destination
- Departure
- Arrival
- Passengers
- Mode
- Van
- Ferry/flight reference
- Estimated cost
- Actual cost
- Status
- Warnings

## 11.11 Conflict centre

List:

- Hard conflicts
- Conditional conflicts
- Unassigned equipment
- Missing routes
- Missing crew
- Overloaded lorries
- Arrival before receiving crew
- Unconfirmed transport
- Provisional competition
- Low timing margin

Each warning must link to the relevant item.

## 11.12 Zoom and density

Full-season zoom may show:

```text
BUILD · ROSKILDE · 11
```

Closer zoom may show:

```text
6V · UP 23 Jun 20:00
Camping on site · Catering
Loads 15, 16, 17
```

The board may use a dedicated horizontal scroll region.

---

# 12. Workflow specifications

## 12.1 Create an enquiry

1. Open Planning Board or Jobs.
2. Drag dates or choose Add Job.
3. Enter name, customer and location.
4. Set status to enquiry or quoted.
5. Enter milestones.
6. Add tent requirements.
7. Generate equipment requirements.
8. Estimate build and strike phases.
9. Check provisional availability.
10. Check direct travel feasibility.
11. Show:
    - Equipment feasibility
    - Crew feasibility
    - Transport feasibility
    - Cost estimate
    - Margin estimate
    - Conflicts
12. Save as provisional.

Do not create hard allocations unless explicitly requested.

## 12.2 Confirm after deposit

1. Open provisional job.
2. Record deposit.
3. Change commercial status.
4. Run conflict check.
5. Show conflicts with confirmed work.
6. Planner approves equipment.
7. Convert approved soft holds to hard.
8. Lock selected plans.
9. Update planning status.

Never silently displace confirmed work.

## 12.3 Allocate equipment

1. View requirements.
2. List compatible candidates.
3. Order candidates by:
   - Availability
   - Predicted location
   - Direct feasibility
   - Timing margin
   - Existing load opportunity
   - Locks
4. Planner accepts or chooses alternatives.
5. Update movement requirements.
6. Recalculate conflicts.

## 12.4 Create a load

1. Select movement.
2. Add load.
3. Assign load number.
4. Choose lorry type or lorry.
5. Choose haulier.
6. Add contents.
7. Show capacity.
8. Enter or calculate times.
9. Calculate route and cost.
10. Save as proposed or booked.
11. Export detail if needed.

## 12.5 Add asset to existing load

1. Open requirement or load.
2. Search loads with compatible route, timing and capacity.
3. Show candidates.
4. Planner selects.
5. Validate continuity.
6. Add asset.
7. Recalculate warnings.
8. Do not alter locked loads without confirmation.

## 12.6 Record actual haulage cost

1. Open load or invoice.
2. Enter invoice reference and date.
3. Enter total.
4. Allocate lines to loads.
5. Record cost categories.
6. Show variance.
7. Update job actual costs.

## 12.7 Create crew move

1. Select people or movement need.
2. Create crew move.
3. Set origin, destination and times.
4. Add journey legs.
5. Assign van.
6. Add passengers.
7. Validate capacity and arrival.
8. Add ferry/flight reference.
9. Save and show on board.

## 12.8 Modify dates by dragging

1. Drag or resize phase.
2. Show proposed dates.
3. Recalculate:
   - Contract compliance
   - Crew conflicts
   - Asset timing
   - Load timing
   - Route feasibility
4. Show impact summary.
5. Confirm or cancel.
6. Preserve locks.
7. Write audit log.

---

# 13. Reports and exports

## 13.1 Seasonal loads list

Columns:

- Load number
- Origin
- Destination
- Departure
- Arrival
- Haulier
- Vehicle type
- Contents
- Job
- Status
- Estimated cost
- Actual cost
- Notes

## 13.2 Load sheet

One printable page per load:

- Load number
- Origin and destination
- Date/time
- Contacts
- Vehicle/haulier
- Contents
- Capacity
- Loading instructions
- Ferry details
- Notes

## 13.3 Crew moves list

Columns:

- Crew move number
- Origin
- Destination
- Departure
- Arrival
- Passengers
- Tentmaster changes
- Van
- Ferry/flight
- Cost
- Notes

## 13.4 Daily crew report

For each date:

- Tentmaster
- Job/activity
- Named crew
- Required count
- Assigned count
- Local crew
- Shortfall
- Daily total

## 13.5 Asset journey report

For a selected asset:

- Date/time
- Location
- Job
- State
- Load
- Previous location
- Next location
- Conflict

## 13.6 Job cost report

- Revenue
- Estimated labour
- Actual labour
- Estimated transport
- Actual transport
- Estimated travel
- Actual travel
- Other costs
- Estimated margin
- Actual margin
- Variance

---

# 14. Seed data

Provide a development seed command.

Seed:

- Oxford Yard
- Tentmasters:
  - Max/Martin
  - Ross
  - Jesse
  - Marley
- Tent family: Kayam
- Configurations:
  - 4-pole
  - 6-pole
  - 10-pole
  - 12-pole
- Equipment types:
  - End
  - Middle
  - Pole
  - Anchor set
  - Ancillary kit
- Example assets:
  - K1, K2, K3
  - M1–M5
  - P1–P20
  - A1, A2
- Standard artic
- Example van
- Example crew
- Example jobs:
  - Roskilde
  - Scotland
  - UK event
- Example loads and crew moves

Mark seed data clearly as demonstration data.

---

# 15. Reference workbook analysis support

Retain the workbook under `reference/`.

V1 does not require a perfect importer.

Create an exploratory script able to:

- Read sheet dimensions
- Read dates from column A
- Read crew-side values
- Read equipment-side values
- Read merged cells
- Read fill colours
- Read comments
- Detect `LD` references
- Detect `CM` references
- Export diagnostic JSON

This script supports reverse-engineering and future migration.

Do not claim perfect automatic import.

---

# 16. Routes and endpoints

## 16.1 HTML routes

Suggested:

```text
/
 /planning
 /jobs
 /jobs/new
 /jobs/{id}
 /jobs/{id}/edit
 /loads
 /loads/{id}
 /crew-moves
 /crew-moves/{id}
 /equipment
 /equipment/{id}
 /crew
 /crew/{id}
 /locations
 /vehicles
 /costs
 /conflicts
 /admin
```

## 16.2 JSON or HTMX endpoints

Examples:

```text
GET  /api/planning/board
POST /api/jobs
PATCH /api/jobs/{id}
POST /api/jobs/{id}/generate-requirements
POST /api/jobs/{id}/check-feasibility
POST /api/equipment-assignments
POST /api/loads
PATCH /api/loads/{id}
POST /api/loads/{id}/items
POST /api/crew-movements
POST /api/routes/calculate
GET  /api/conflicts
```

---

# 17. Non-functional requirements

## 17.1 Reliability

- Use transactions for multi-record changes.
- Avoid partial allocations after errors.
- Add constraints and indexes.
- Handle missing API keys.
- Keep manual planning usable without routing.

## 17.2 Performance

Target:

- Several hundred jobs
- Several hundred equipment assets
- Several thousand assignments and movements
- Full-season board loads in a few seconds on a normal laptop

Use date-range queries.

## 17.3 Portability

Must run on:

- macOS
- Windows
- Linux

Use `pathlib`.

Avoid platform-specific shell assumptions.

## 17.4 Backup

Provide:

- Documented SQLite path
- Backup command or button
- JSON export
- Restore instructions

## 17.5 Security

- Bind to localhost by default.
- Do not expose debug mode publicly.
- Use environment variables.
- Do not commit secrets.
- Validate imports.
- Escape notes in templates.

## 17.6 Accessibility

- Do not use colour alone.
- Use labels, icons and patterns.
- Keyboard-accessible forms.
- Good contrast.
- Visible focus states.

---

# 18. Testing requirements

## 18.1 Unit tests

Test:

- Tent requirement expansion
- Date validation
- Equipment compatibility
- Hard and soft overlap
- Travel feasibility
- Capacity calculation
- Transport estimate
- Crew cost
- Job margin
- Lock preservation
- Route-cache keys

## 18.2 Integration tests

Test:

- Create job and tent requirement.
- Generate components.
- Assign equipment.
- Create movement and load.
- Add load contents.
- Detect overload.
- Assign crew.
- Detect crew overlap.
- Confirm provisional job.
- Preserve locks.
- Record actual cost.
- Export load list.

## 18.3 Acceptance scenarios

### A. Modular tent

Given one 10-pole configuration, the system generates 2 ends, 4 middles and configured poles/ancillary requirements.

### B. Equipment conflict

Given K1 is hard-assigned to Job A, an overlapping assignment to Job B produces a hard conflict.

### C. Provisional competition

Given K1 is softly held for a quotation, a confirmed job may compete for it but the system reports a conditional conflict.

### D. Travel infeasible

Given M1 is released in Denmark too late to reach Scotland, the system reports a transport conflict.

### E. Load capacity

Given a lorry with 12 section units, adding 13 units marks it over capacity.

### F. Receiving crew

Given a load arrives before receiving crew, show a warning.

### G. Crew overlap

Given one person is assigned to overlapping confirmed phases, show a hard conflict.

### H. Confirmation

Given a quoted job with soft holds, confirmation converts approved holds to hard without changing unrelated locked work.

### I. Cost variance

Given an estimate and later invoice, show estimate-versus-actual variance.

### J. Asset continuity

Given one asset moves through several jobs, its timeline must contain no unexplained jump.

---

# 19. Implementation milestones

Keep the app runnable after every milestone.

## Milestone 1: Foundation

- Project setup
- FastAPI
- SQLAlchemy
- Alembic
- SQLite
- Templates
- Configuration
- Tests
- Seed command
- README

## Milestone 2: Administration

- Locations
- Tent families
- Configurations
- Equipment types
- Assets
- Tentmasters
- Crew
- Memberships
- Lorry types
- Vans
- Hauliers

## Milestone 3: Jobs and phases

- Job CRUD
- Statuses
- Milestones
- Tent requirements
- Expansion
- Build/strike phases
- Job detail

## Milestone 4: Crew planning

- Crew assignments
- Headcount
- Daily totals
- Conflict detection
- Basic crew board
- Drag-to-create

## Milestone 5: Equipment planning

- Equipment requirements
- Asset assignment
- Soft/hard allocation
- Locks
- Asset timeline
- Overlap conflicts

## Milestone 6: Loads and movement

- Equipment movements
- Loads
- Load items
- Capacity
- Load lifecycle
- Loads export
- Oxford staging

## Milestone 7: Routing and feasibility

- Routing interface
- OpenRouteService adapter
- Manual fallback
- Geocoding
- Route cache
- Feasibility
- Timing margin

## Milestone 8: Crew moves and vans

- Crew movements
- Journey legs
- Passengers
- Van capacity
- Ferry/flight
- Export

## Milestone 9: Costing

- Labour estimates
- Transport estimates
- Actual load costs
- Invoice allocation
- Margins

## Milestone 10: Combined board

- Synchronized crew/equipment board
- Compact day rows
- Sticky headers
- Status styling
- Highlighting
- Side panels
- Zoom/filtering

## Milestone 11: Hardening

- Audit logs
- Backup/export
- Validation
- Integration tests
- Documentation
- Packaging
- Performance review

---

# 20. Codex working instructions

Create `AGENTS.md` containing:

1. Read `SPECIFICATION.md` before architectural changes.
2. Keep the app runnable after each milestone.
3. Do not silently break previous milestones.
4. Add or update tests with every business-rule change.
5. Use migrations for schema changes.
6. Do not store secrets in the repository.
7. Preserve manual locks.
8. Never silently alter confirmed operational assignments.
9. Keep calculations in Python services.
10. Prefer maintainable code over premature abstraction.
11. Record assumptions in `DECISIONS.md`.
12. Record unresolved questions in `OPEN_QUESTIONS.md`.
13. Do not invent production business data.
14. Use the workbook only as a reference unless explicitly asked to import.
15. Run tests before declaring a milestone complete.

Suggested commands:

```bash
python -m pytest
python -m ruff check .
python -m mypy app
alembic upgrade head
```

Do not block initial progress on exhaustive type coverage.

---

# 21. Definition of V1 complete

V1 is complete when a planner can:

1. Run the app locally.
2. Define locations, equipment, Tentmasters, crew, lorry capacities, vans and hauliers.
3. Create a provisional job with contract dates and tent requirements.
4. See generated equipment requirements.
5. Assign named physical assets.
6. See overlap and travel conflicts.
7. Assign Tentmaster and crew.
8. See daily crew totals.
9. Create numbered loads.
10. Validate lorry capacity.
11. Calculate distance and HGV travel time where API access exists.
12. Use manual route data where it does not.
13. Create crew moves with vans, ferries or flights.
14. View the season on a combined board.
15. Confirm a job without displacing locked confirmed plans.
16. Export loads and crew moves.
17. Estimate costs and record actual haulage costs.
18. Inspect the journey of an asset such as K1.
19. Back up the database.
20. Run a meaningful automated test suite.

---

# 22. Open questions

Record these in `OPEN_QUESTIONS.md`.

1. Exact definition of Tentmaster: team, lead person or both.
2. Exact compatibility rules between tent families.
3. Whether poles are individually tracked or grouped.
4. Whether anchors and ancillary gear are individual or quantity-based.
5. Exact lorry capacity dimensions used in practice.
6. Exact meaning of `UP`, `DN` and other abbreviations.
7. Crew overtime and travel-pay rules.
8. Whether a load may arrive without Kayam crew if another party can receive it.
9. Cost allocation between the previous and next job.
10. Whether every confirmed quotation creates hard reservations immediately.
11. Whether a job may use several independent build teams.
12. Timezone handling for continental work.
13. Whether local crew names are tracked.
14. Whether invoices need VAT handling.
15. How maintenance blocks equipment.
16. Whether sections may remain erected after maintenance crew leave.
17. Whether vans can carry equipment affecting lorry planning.
18. Preferred UI term: job, event, show, contract or location.
19. Load-number season rollover.
20. Future hosted database choice: PostgreSQL or MySQL.

Use conservative, configurable defaults where practical.

---

# 23. Final product principle

The workbook works because experienced planners can look at one continuous visual plan and reason about the whole season.

The application must improve reliability without removing that perspective.

The guiding principle is:

> Data is entered as jobs, requirements, assignments and movements, but users experience it as a continuous seasonal flow of people, equipment and transport.

V1 should make that flow structured, searchable, testable and conflict-aware while preserving planner control.
