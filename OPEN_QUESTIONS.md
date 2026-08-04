# OPEN_QUESTIONS.md

# Open Business and Product Questions

These questions are not blockers for project scaffolding. They must be resolved before the affected feature is treated as production-ready.

Use this format when adding questions:

```text
## Q000 — Question title

Status: Open
Owner:
Needed by:
Current assumption:
Decision:
Notes:
```

---

## Q001 — What precisely is a Tentmaster? — RESOLVED

**Status:** Resolved (D029)  
**Needed by:** Crew administration and crew-board implementation  
**Question:** Is a Tentmaster primarily a team, the lead person, or both?

**Resolution:** A Tentmaster is a named individual leading a crew, not an abstract team —
confirmed via `reference/LOADS 26 V8.xlsx`'s `TM DETAILS` sheet (Martin Peers=MP, Ross Markham=RM,
Jesse Thompson=JT, Marley Yuill=MY). A `JobPhase` is assigned to a Tentmaster, and its headcount/
named crew are derived from that Tentmaster's current `TentmasterMembership` roster — see
SPECIFICATION.md §4.3.

---

## Q002 — Which tent families and configurations exist? — LARGELY RESOLVED

**Status:** Resolved (D030) — one gap remains, see below  
**Needed by:** Production seed data  
**Question:** What are the complete tent families, sizes and component templates?

**Resolution:** Named "configuration" templates (e.g. "Kayam 10-pole") do not reflect how the
business actually books tents — confirmed by the owner directly: many different section
combinations produce the same pole count, so a tent is described as a section-code sequence (e.g.
K-M-M-M-K), not a size template. The real equipment taxonomy is now seeded: Kayam (K, M, m, S, T,
SC ends/middles/triangles/covers, P king pole pairs) and Valhalla (V, VOE, VNE, plus X poles —
family assignment for X is unconfirmed, see Q041). See D030.

**Remaining gap:** Valhalla poles are not tracked as named assets and are not derived via the
Kayam-style family pole formula. Owner direction (2026-08-04, Q040): treat them as untracked
linked quantity — e.g. 1 Valhalla pole per Valhalla End (VOE/VNE) and 2 per Valhalla Middle (V) —
so they show for truck loading only. Not configured in the DB yet.

---

## Q003 — What equipment is compatible?

**Status:** Open  
**Needed by:** Equipment suggestion engine  
**Question:** Which ends, middles, poles and ancillary items can be combined across variants or tent families?

**Current assumption:** Exact equipment type match unless an explicit compatibility record says otherwise.

---

## Q004 — How are poles tracked? — RESOLVED

**Status:** Resolved (D030)  
**Needed by:** Equipment model  
**Question:** Are poles individually numbered, grouped into bundles, or treated as quantities?

**Resolution:** Individually numbered, but tracked as pairs — one asset (e.g. "P4") represents 2
physical poles. Modelled via `EquipmentType.pack_size` (2 for the Kayam King Pole type); the
derived pole count from a section sequence is divided by `pack_size` to get the asset quantity.

---

## Q005 — How are anchors and ancillary equipment tracked?

**Status:** Open  
**Needed by:** Equipment model  
**Question:** Are these individually named assets, complete kits or quantities?

**Current assumption:** Support individual and quantity-tracked types.

---

## Q006 — What capacity units are used for lorries?

**Status:** Open  
**Needed by:** Load-capacity production rules  
**Question:** How many ends, middles, poles and ancillary items fit on each real lorry type, and what stacking combinations matter?

**Current assumption:** Use configurable section, pole, ancillary and weight units.

---

## Q007 — What do workbook abbreviations mean?

**Status:** Open  
**Needed by:** UI terminology and future import  
**Question:** Confirm meanings of `UP`, `DN`, `LD`, `UNLD`, `CM`, arrow notation and any other operational shorthand.

**Current assumption:**

- `LD`: load
- `UNLD`: unload
- `CM`: crew move
- `UP`: contractual tent-up milestone
- `DN`: likely down/strike milestone, unconfirmed

---

## Q008 — What exact contract milestones are required?

**Status:** Open  
**Needed by:** Job editor  
**Question:** Are site access, must-be-up, show start, show end, strike available and site clear sufficient?

**Current assumption:** Store all six, with show dates and site-clear deadline optional.

---

## Q009 — How should build and strike duration be calculated?

**Status:** Open  
**Needed by:** Phase generation  
**Question:** What real data relates tent size, crew size, site conditions and build/strike duration?

**Current assumption:** Configuration default plus planner override. Do not pretend the first formula is exact.

---

## Q010 — How does ground type affect work?

**Status:** Open  
**Needed by:** Later feasibility and costing  
**Question:** Do concrete, rock, soft ground and other conditions alter equipment, crew or duration requirements?

**Current assumption:** Store structured ground type and notes but do not automate impact initially.

---

## Q011 — What are the crew pay rules?

**Status:** Deferred (owner 2026-08-04: skip costing for now)  
**Needed by:** Production labour costing  
**Question:** Confirm hourly rate, overtime, travel pay, daily allowance and any minimum-day rules.

**Current assumption:** Configurable simple rates with manual adjustments; no payroll. Costing UI
and rules exist as a V1 baseline but are not a current priority.

---

## Q012 — How should travel cost be allocated between jobs?

**Status:** Deferred (owner 2026-08-04: skip costing for now)  
**Needed by:** Job margin  
**Question:** Does a move from Job A to Job B belong to A, B, both, or a seasonal overhead budget?

**Current assumption:** Require explicit allocation; do not distribute automatically.

---

## Q013 — Can third parties receive loads?

**Status:** Open  
**Needed by:** Receiving-crew validation  
**Question:** May a load arrive before Kayam crew when a customer, local crew or haulier representative can receive it?

**Current assumption:** Warn unless an authorised receiving party or override is recorded.

---

## Q014 — When does confirmation create hard allocations?

**Status:** Open  
**Needed by:** Job confirmation workflow  
**Question:** Does deposit receipt immediately reserve all selected equipment, or is separate planner approval required?

**Current assumption:** Deposit changes commercial status; planner approval converts selected soft holds to hard allocations.

---

## Q015 — May one job have several simultaneous Tentmasters? — RESOLVED

**Status:** Resolved (D036)  
**Needed by:** Job phases and board  
**Question:** Can separate tents or phases at one job be handled by independent teams?

**Resolution:** Yes, confirmed. Each tent gets its own `UP` `JobPhase` tied to that specific tent
(`job_tent_requirement_id`), independently assignable to a Tentmaster — a job with several tents
can have a different Tentmaster on each, or split one tent's Up window across several
Tentmasters over time (a crew handover mid-contract). `BUILD`/`BREAK` phases stay job-level since
the same crew typically builds/strikes every tent on a job together.

---

## Q016 — How should local crew be represented? — RESOLVED

**Status:** Resolved (D036)  
**Needed by:** Crew planning  
**Question:** Are local crew tracked by names, supplier, headcount only, or a mixture?

**Resolution:** Headcount only, no names and no supplier field — the old "named crew and
placeholders" assumption was superseded. Local/hired crew is booked as a job-level, date-ranged
`LocalCrewBooking` (`headcount`, `start_at`, `end_at`, `notes`), joining whichever phases overlap
its window. This replaced the earlier per-phase `CrewAssignment` placeholder mechanism entirely.

---

## Q017 — How is maintenance cover represented?

**Status:** Open  
**Needed by:** Job phases  
**Question:** Does maintenance cover reserve a minimum crew continuously, at specified windows, or on call?

**Current assumption:** Void — D036 removed `PhaseType.MAINTENANCE` entirely (only `SHOW`/`STRIKE`
were ever actually auto-generated as their own phase type, and both are now folded into `UP`/
`BREAK`). Only a job-level `maintenance_cover_required` boolean survives, with no mechanism yet for
how that boolean actually reserves crew. The original question stands, but any answer needs a new
mechanism designed from scratch, not "explicit maintenance phases."

---

## Q018 — How does maintenance affect equipment availability?

**Status:** Open  
**Needed by:** Asset state  
**Question:** Which maintenance types block use, and how is an asset returned to service?

**Current assumption:** Maintenance creates an unavailable interval until marked complete.

---

## Q019 — Can vans carry operational equipment?

**Status:** Open  
**Needed by:** Van and load planning  
**Question:** Can crew vans carry poles, anchors or ancillary items, reducing lorry requirements?

**Current assumption:** Vans have optional cargo capacity but do not automatically substitute for loads.

---

## Q020 — What are the true lorry cost rules?

**Status:** Deferred (owner 2026-08-04: skip costing for now)  
**Needed by:** Transport estimates  
**Question:** Are prices based on route, mileage, minimum charge, number of days, ferry, waiting or negotiated quote?

**Current assumption:** Support manual estimates and configurable rate-card formulas.

---

## Q021 — Is VAT required for invoice tracking?

**Status:** Deferred (owner 2026-08-04: skip costing for now)  
**Needed by:** Supplier invoice feature  
**Question:** Should amounts be stored net, gross or both?

**Current assumption:** Store operational cost amounts without full VAT accounting in V1.

---

## Q022 — What load numbering scheme is used?

**Status:** Open  
**Needed by:** Loads  
**Question:** Do load numbers restart every year, and are numbers shared across every haulier?

**Current assumption:** Unique within an operational season.

---

## Q023 — What crew-move numbering scheme is used?

**Status:** Open  
**Needed by:** Crew moves  
**Question:** Do crew-move numbers restart each season?

**Current assumption:** Unique within an operational season.

---

## Q024 — What is the operational season boundary?

**Status:** Open  
**Needed by:** Board defaults and numbering  
**Question:** Is a season a calendar year, summer season or configurable date range?

**Current assumption:** Configurable season record; default to calendar year until confirmed.

---

## Q025 — Which term should the UI prefer?

**Status:** Open  
**Needed by:** User-facing copy  
**Question:** Should the main entity be called Job, Event, Show, Contract or Location?

**Current assumption:** Use `Job` internally and initially in the UI; location remains the physical place.

---

## Q026 — What route-risk margins are appropriate?

**Status:** Open  
**Needed by:** Feasibility warnings  
**Question:** How much spare time makes a movement green, amber or red?

**Current assumption:**

- Green: at least 24 hours
- Amber: 6–24 hours
- Red: under 6 hours or impossible

Make configurable.

---

## Q027 — What loading and unloading allowances apply?

**Status:** Open  
**Needed by:** Travel feasibility  
**Question:** Are allowances based on load size, location or lorry count?

**Current assumption:** Configurable location and lorry-type defaults with manual override.

---

## Q028 — How should ferry and border time be estimated?

**Status:** Open  
**Needed by:** International route feasibility  
**Question:** Use fixed allowances, route-specific values or manual planning?

**Current assumption:** Manual or configurable route allowance in V1.

---

## Q029 — Does every event require crew to remain on site?

**Status:** Open  
**Needed by:** Crew phase generation  
**Question:** Which shows require maintenance crew, and when may build crew leave?

**Current assumption:** Explicit job setting and maintenance phases.

---

## Q030 — Which database should hosted production use?

**Status:** Open  
**Needed by:** Hosted deployment  
**Question:** PostgreSQL or MySQL?

**Current assumption:** Keep the application portable. PostgreSQL is the likely default unless existing infrastructure prefers MySQL.

---

## Q031 — What permissions are needed?

**Status:** Open  
**Needed by:** Hosted multi-user version  
**Question:** Are there planners, administrators, read-only staff, finance users and operational users?

**Current assumption:** Basic admin/user structure only in V1.

---

## Q032 — What exports must match existing formats exactly?

**Status:** Open  
**Needed by:** Reports  
**Question:** Do hauliers or staff require a particular load-list or crew-move layout?

**Current assumption:** Provide clear CSV and printable views, then refine from examples.

---

## Q033 — Is historical actual movement required?

**Status:** Open  
**Needed by:** Operations/history distinction  
**Question:** Must the system record what actually happened separately from the committed plan?

**Current assumption:** Fields exist for actual load times and costs; broader actual asset tracking can follow.

---

## Q034 — What backup experience is preferred?

**Status:** Open  
**Needed by:** Packaging  
**Question:** Command-line backup, admin button, automatic dated backups, or all three?

**Current assumption:** Admin-triggered and command-line backup in V1.

---

## Q035 — How should provisional quotes compete?

**Status:** Open  
**Needed by:** Sales-risk display  
**Question:** Should confidence percentage affect which provisional job is preferred?

**Current assumption:** Display competition and confidence but do not automatically choose a winner.

---

## Q036 — Can Tentmaster membership change during a day? — RESOLVED

**Status:** Resolved  
**Needed by:** Crew administration and later crew scheduling  
**Question:** May a crew member finish with one Tentmaster and join another on the same calendar
date, and if so must the handover be recorded at a specific time?

**Decision:** Yes. `TentmasterMembership.end_at` is exclusive ("first day no longer active"), so a
crew member can end with one Tentmaster and start with another on the same calendar date; no
specific time-of-day is recorded, only the date. Confirmed with the product owner as part of the
crew-model rework (see `DECISIONS.md` D023). Implemented in migration `babee1b7c057`.

---

## Q037 — How long must audit and backup data be retained?

**Status:** Open  
**Needed by:** Production operations and privacy policy  
**Question:** What retention, deletion and access-control rules apply to audit records, database
backups and JSON exports containing staff or supplier information?

**Current assumption:** Retain audit records indefinitely in local V1 and leave backup retention to
the planner. Define an encrypted automated retention policy before hosted deployment.

---

## Q038 — What quantity of side poles and anchor stillages does a Kayam 20M Middle need? — RESOLVED

**Status:** Resolved  
**Needed by:** Accurate loading lists (D030)  
**Question:** An M implies some quantity of side poles and anchor stillages, per the owner, but no
exact numbers were given (only that an M implies exactly 2 bale rings, which is configured).

**Resolution (side poles):** `reference/kay.parts.csv` (owner-supplied, 2026-08-03) gives a
complete side-pole count per section: K=30, m=12, M=16, T=3, SC=1, s=18 — configured via
`app.commands.seed.LINKED_PARTS_MATRIX` and applied to `instance/kayam.db` with
`kayam-sync-equipment-taxonomy`.

**Resolution (anchor stillages):** Dropped (owner, 2026-08-04) — do not model anchor stillages as
per-section linked equipment. `EquipmentType.ANCHOR_STILLAGE` may remain in the catalogue unused;
no further work required.

---

## Q039 — Do section types other than M and P (king pole) have their own linked equipment? — RESOLVED for Kayam family

**Status:** Resolved for K/m/M/T/SC/s/P/X (D038 sync, 2026-08-03) — Valhalla (V/VOE/VNE) still open  
**Needed by:** Accurate loading lists (D030)  
**Question:** S (Siam End), m (15m Middle), T (Triangle), SC (Stage Cover), V (Valhalla Middle),
VOE/VNE (Valhalla ends) may each imply their own hidden equipment, the same way M and P do.

**Resolution:** `reference/kay.parts.csv` gives a complete per-section parts matrix for every
Kayam-family section/pole code (K, m, M, T, SC, s, P, X) — 22 new linked `EquipmentType` rows
(guys, tifors, cables, stretchers, walls, stakes, ratchets, caps, base plates, hinges, etc.) plus
their `EquipmentLink` ratios, configured via `LINKED_PARTS_MATRIX` in `app/commands/seed.py` and
applied live via `kayam-sync-equipment-taxonomy`. Valhalla (V/VOE/VNE) has no equivalent CSV yet —
still genuinely unconfigured, and per the owner "isn't so modular" so may never get a comparably
granular parts list (see Q040/Q042).

**Note:** `kay.parts.csv`'s "Standard Guys" (P=3, X=3) and "1.6/3.2 Ton Tirfor" (P=3 each) don't
cleanly map onto the pre-existing placeholder `SIDE_GUY`/`TIFOR_1_5T` types (P=2 each, marked
"DEMONSTRATION DATA — confirmed ratio" despite not actually being confirmed) — left as separate
types rather than merged/renamed, since it's not certain they're the same physical item. Owner
should confirm whether `SIDE_GUY`/`TIFOR_1_5T` should be deactivated in favour of the new ones.

---

## Q040 — What is Valhalla's pole formula and pole equipment type? — RESOLVED (direction)

**Status:** Resolved as product direction (2026-08-04) — not yet configured in seed/DB  
**Needed by:** Valhalla job bookings / truck loading lists (D030, load engine)  
**Question:** Kayam's formula (poles = sections×2−2, fulfilled by the King Pole pair type) was
confirmed by the owner. Valhalla's equivalent — including whether it uses the same formula, and
which equipment type (X Poles? something else?) fulfils it — was not.

**Resolution:** Valhalla poles **are not tracked as named assets**. They still "go in the trucks"
and should appear as quantity for loading, not as individual stock codes. Owner direction:

- Do **not** wire `TentFamily.pole_equipment_type_id` / Kayam-style derived-pole formula for
  Valhalla.
- Prefer linked components: e.g. **1 Valhalla pole per Valhalla End (VOE/VNE)** and **2 Valhalla
  poles per Valhalla Middle (V)** — exact type code/name still to choose when configured.
- Until that link is added, booking a Valhalla sequence correctly derives no named poles (by
  design, not a bug).

**Also (lorry packing, not pole formula — see Q042):** whole-tent flatbed examples remain the
capacity model for Valhalla (6-pole = 3 flatbeds, etc.), separate from this linked-pole quantity.

---

## Q041 — When is "X Poles" used instead of the Kayam King Pole?

**Status:** Open (less urgent after Q040)  
**Needed by:** Pole requirement accuracy if X appears on real loads  
**Question:** X Poles (pair) was listed by the owner alongside the Kayam King Pole as a distinct
pole type, with no stated tent family or usage rule.

**Current assumption:** Seeded with no `tent_family_id` (family-agnostic) and not wired as any
family's derived pole type. Q040 clarifies Valhalla poles are a separate untracked linked
quantity — **X is not the Valhalla pole answer**. Leave X as a catalogue type until a real usage
rule is needed; do not invent one.

---

## Q042 — Lorry-loading capacity data (owner-supplied 2026-08-03) — recorded, not yet implemented

**Status:** Confirmed input data (re-confirmed by owner 2026-08-04) — recorded for the automatic
load-design/routing engine (top-roadmap item 5, D014). Not implemented in capacity calculations
yet; not a schema change. Also referenced from `LOAD_ENGINE_DESIGN.md`.

**Vehicle capacity (confirmed):**

- Curtainsider: **6 points**
- Flatbed: **7.2 points**

**Points per Kayam-family section/pole type** (owner-supplied, applies to sections/poles only —
not the linked parts in `kay.parts.csv`/Q038/Q039, which are a separate, much smaller-unit system):

| Type | Points |
| --- | --- |
| K | 1.2 |
| m | 1 |
| M | 1 |
| T | 1 |
| s | 1.2 |
| P | 1.2 |
| X | 1.4 |

No point value given for `SC` (Stage Cover) — not yet known whether it's omitted deliberately
(never point-loaded the same way) or just not mentioned yet.

**Valhalla is explicitly a different system** — the owner's own words: "Valhalla is slightly
different, because it's not so modular... we don't list out Poles etc separately, only VOE / VNE
/ V." No points-per-section table exists for Valhalla; instead three worked examples of whole
tents/additions mapped directly to flatbed counts:

- 6-pole `VOE-V-V-VOE` (4 sections) = 3× Flatbed
- 6-to-10-pole conversion, adding `V-V` (2 sections) to an existing 6-pole tent = 2× Flatbed
- 12-pole `VOE-V-V-V-V-V-VOE` (7 sections) = 5× Flatbed

**Attempted formula (unconfirmed — needs the owner's check, not verified against real loading):**
end sections (`VOE`/`VNE`) = 1 flatbed each, dedicated; middle sections (`V`) pair up, 2 per
flatbed, rounded up. This exactly reproduces both *standalone-tent* examples: 6-pole = 2 ends (2
FB) + 2 middles (⌈2/2⌉=1 FB) = 3 FB ✓; 12-pole = 2 ends (2 FB) + 5 middles (⌈5/2⌉=3 FB) = 5 FB ✓.
The "6-to-10 conversion" example (+2 FB for 2 added V's) only fits this formula if read as an
*incremental, separately-packed* shipment rather than a full repack of the whole 6-section tent
together (which this formula would price at only 2 FB total for middles, i.e. +1 FB, not +2) —
plausible for a real field top-up, but not confirmed. Do not build against this without the
owner's sign-off; get more worked examples first if possible.

**Where this eventually plugs in:** `Load` capacity today (SPECIFICATION.md §8.9) is
section/pole/ancillary *unit counts* and weight, not a points system — this is a different,
finer-grained model that would need reconciling with (or replacing) §8.9 once the load-design
engine's actual design is agreed.

---

## Q043 — Do manual ancillary items (e.g. stake basher) auto-track through the season with the kit?

**Status:** Open — **behaviour confirmed for next session** (owner asked 2026-08-04)  
**Needed by:** Season load generator V2 / load-edit UX  
**Question:** If a planner adds something like a stake basher (or other ancillary) onto an early
load, should later job→job legs and the final return-to-Yard automatically carry that item, or
must it be managed load-by-load?

**Current behaviour (V1 — do not treat as a bug):**

- Season generate only auto-packs **sections + poles** (quantity-by-type free pool). Linked kit is
  implied on the load sheet, not packed as separate trailer lines; ancillaries (stake basher,
  rock drill, crew tent, etc.) are **not** in the free-pool chain.
- Adding an ancillary to load L*n* keeps it on **that load only**.
- **Generate season loads** again **deletes unlocked** auto movements/loads and recreates them —
  manual lines on unlocked auto loads are **wiped** unless the load (or movement) is **locked**.
- Job→job and Yard-return legs therefore do **not** auto-inherit a stake basher from an earlier
  load.

**Workarounds today:** lock the load(s) you hand-edited; re-add after regen; or add the item on
each leg that should carry it.

**Candidate product options for a later session (not decided):**

1. **Lock-on-edit** — touching an auto load auto-locks it (or prompts) so regen preserves it.
2. **Carry ancillaries with parent stock** — when regenerating, any non-section/pole items on a
   donor leg are re-attached to the next outbound leg(s) that take that kit (and eventually
   Yard-return).
3. **Job-level ancillary requirements** — planner lists stake bashers etc. on the job; generate
   packs them onto inbound/outbound like sections.

**Decision:** none yet — pick an option (or hybrid) with the owner before implementing.

**Notes for next session:** Owner wants this remembered; season board job side panel now shows
inbound/outbound loads (contents + dates) which makes the gap more visible.

---

## Q044 — What does auto crew-move generation actually do, and is it correct?

**Status:** Open — **check next session** (owner request 2026-08-04)  
**Needed by:** Confidence in “Generate season loads & crew moves”  
**Question:** Does the auto crew-move path produce the right Tentmaster travel (between which
jobs/phases, when, which mode), and what does regen do to existing crew moves?

**Where to look:**

- `SeasonPlanService._generate_crew_moves` / `generate(include_crew_moves=True)` in
  `app/services/season_plan.py`
- Clears unlocked auto crew moves (notes marker) then recreates
- UI: **Generate season loads & crew moves** on `/loads`

**Current assumption (from V1 design, verify against real data):** consecutive Tentmaster phase
visits at different sites get a planned crew move; locked/non-auto moves kept.

**Next session task:** Run generate on live season data, inspect created crew moves on the board /
crew UI, and either confirm behaviour or list concrete fixes.
