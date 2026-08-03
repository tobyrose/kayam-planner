# Load Diagram & Auto-Routing Engine — Design Notes

**Status:** Design conversation in progress. Nothing in this document is built. This is the
owner's "crack it" feature after ~30 years of doing it by hand in Excel — deliberately deferred in
the original spec (D014) and getting its own design pass before any code, per the owner's explicit
request on 2026-08-03. This file is the durable record of that conversation so it survives context
resets — update it in place as the conversation continues, don't let detail live only in chat.

**Feeds:** `IMPLEMENTATION_PLAN.md` top-roadmap item 5 ("Automatic load-design/routing engine with
manual override"). Related open items: `OPEN_QUESTIONS.md` Q042 (lorry-loading capacity data),
Q012 (travel cost allocation), Q019 (van cargo), Q020 (lorry cost rules), Q026–028 (route
margins/allowances).

---

## 1. The Loads Diagram

### 1.1 What it's for

The owner's own words: "This diagram is how we work out the most efficient routes and generate
the 'Loads List' for hauliers — it's VERY manual and VERY prone to error — it's easy to lose
sections or 'magic' things to places." Two reference images were supplied and read directly:

- `reference/kay_loads_diagram.png` — a full season, hand-built in Excel.
- `reference/kay.loads.close.example.png` — a hand-drawn close-up of one small section of the
  same idea, walked through verbally.

What follows is my read of those two images plus the owner's explanation, written out in full so
it can be checked rather than assumed correct.

### 1.2 Structure, as I currently understand it

- **Dates run down the left**, one row per day — same convention as the season board and the
  existing `/planning/flow` diagram.
- **Columns are jobs and yard-occupancy, not fixed lanes.** A job's column starts on the day its
  first load's equipment arrives and ends when its last load departs — the same "expand columns as
  needed, shrink when not" interval-packing idea already built for the season board's Unassigned/
  Quoted lane (D038), explicitly confirmed by the owner as the right model here too: **"This is
  similar to how we were going to do the unassigned jobs. Expand columns so jobs fit, reduce
  columns if not needed. NOT one job per column."** Gaps between a job's column and the next thing
  that column-slot holds represent travel time, and the whole diagram reads left-to-right as
  "whatever's physically closest together in time," not one column per physical site.
- **The Yard is a colour, not a column.** A light-blue background marks Yard occupancy, and it
  recurs in many different column positions throughout the sheet, not one fixed lane. Whenever
  equipment is sitting in the Yard, that equipment's codes are re-listed on every day it's still
  there, so a planner can read straight down a blue block and see exactly what's in the yard on
  any given date, *provided* the loads that brought it in have already arrived and the loads
  taking it out haven't left yet. This is the single hardest part of the diagram to translate into
  a rendering algorithm — see the open question in §1.5.
- **A job's box lists real equipment codes, not just a section-sequence summary.** Each job's
  column shows: a small numbered header (the load number(s) delivering it), the actual codes
  arriving (e.g. `K8`, `P4`, `M26`, `sb1`), the job name, then — lower down in the *same* box — the
  same-style list again for what's *leaving*. Owner's words: **"We show all the sections coming in
  ... copy all the things underneath in the same box and show them going out."** Arriving and
  departing lists can differ (not everything that arrives leaves together, or leaves for the same
  next destination).
- **Colour marks provenance/destination, not job identity.** In the close-up example, an orange
  tint follows one batch of equipment from the Yard into Catalyst; a green tint follows a
  different batch from "Another Job" onward. This is what lets a planner visually trace "which
  things are leaving and which are arriving and where they're travelling to" at a glance, per the
  owner's description.
- **Small numbered headers above a block are load numbers.** E.g. "1 2" above Catalyst's incoming
  block, "15 16 17" above Silverstone's. The worked example: **"Load 15, 16, 17 contains all
  equipment we need for Silverstone ... the things we need at Silverstone adds up to 3 trailers —
  so that's what we show."** i.e. the number of columns/cells in a load-number header block is
  literally the number of lorries needed to carry that job's requirement, computed from the
  points-per-lorry capacity math already recorded in `OPEN_QUESTIONS.md` Q042.
- **Clicking an equipment code should trace it through the whole season.** Owner's example:
  **"we could click on K8 for example — it would highlight and we could track exactly how that
  section flows through the season."** This is the same click-to-highlight interaction the season
  board already has for jobs (D033) and that the flow diagram/board.js used to have for individual
  assets before the season-board rebuild dropped the separate Equipment column (D038) — it needs
  to come back specifically for this diagram (see §3, implementation note).

### 1.3 Worked example (Yard → Silverstone), verbatim from the owner

> Taking Yard to Silverstone as an example: these places are quite close, we load on 18th June —
> arrive 19th June. Load 15, 16, 17 contains all equipment we need for Silverstone — so split of
> things will be up to the Tentmaster. Critically — the things we need at Silverstone adds up to
> 3 trailers — so that's what we show. We show all the sections coming in (in purple here) line —
> copy all the things underneath in the same box and show them going out.

Reading this against the full diagram: Silverstone's box does show a "15 16 17" header, a purple
arrival list, the "SILVERSTONE" label, then a repeated departure list lower in the same box —
matches the general pattern in §1.2.

### 1.4 Table vs. D3 — recommendation

**Recommendation: build it as a table, the same way as the season board and `/planning/flow`, not
with D3.** Reasoning:

- Every individual piece this diagram needs has already been built and proven to work as plain
  server-rendered HTML in this codebase, with no charting library: dates-down-one-row-per-day
  (season board, D027); one column per entity with contiguous multi-day blocks (season board,
  D031; flow diagram, D032); dynamic column count via interval-packing so unrelated items don't
  each get their own permanent lane (season board Unassigned/Quoted, D038); multiple stacked
  detail lines inside one block (season board `BoardBlock.detail_lines`, D038); an SVG line overlay
  drawn on top of a table for cross-column journeys (flow diagram, D032); click-to-highlight by a
  shared data attribute across every block on the page (`board.js`, D033, previously supported
  asset codes too before D038 removed the separate Equipment column — reinstating that for this
  diagram is a small, known change, not new design).
- The one genuinely new piece is the Yard's *recurring, multi-instance* column behaviour (§1.5) —
  but that's a harder packing problem, not a rendering-technology problem. A table can still render
  whatever the packing algorithm decides; D3 wouldn't make the packing decision any easier.
- `AGENTS.md`'s own rule — JavaScript stays presentational, structured records drive everything —
  argues against introducing a heavy client-side data-viz framework for something a template loop
  can already produce. It would also be the first non-vanilla-JS dependency in the stack
  (FastAPI + Jinja2 + HTMX + vanilla JS today).
- Fallback: if, once built, the Yard's repeated-column behaviour genuinely can't read clearly in a
  strict table grid, the SVG-overlay technique already used for flow-diagram journey lines can be
  extended rather than reaching for D3 wholesale.

### 1.5 Open questions on the diagram itself (need the owner's check before building)

1. **How does the Yard get its column(s)?** Is it one dynamically-packed lane per concurrent
   "batch" of yard stock (mirroring the job interval-packing exactly, just for yard-resident
   equipment groups instead of jobs), or something else? The full diagram shows the Yard's blue
   background jumping to very different horizontal positions over the season — is that positional
   meaning intentional (e.g. "near" the jobs it's about to feed) or just wherever Excel had a free
   column that week?
2. **Load-number header semantics.** In the close-up example a header reads "8 8 8" — three cells,
   the same number repeated three times, directly above a 3-wide box. Does that mean *one* load
   (load 8) that needed 3 trailers, all sharing one load number, or three separate loads that
   happen to be numbered sequentially and the image just repeats "8" as a mislabel/shorthand? This
   matters because the existing `Load` model is one row per lorry/trailer with its own
   `load_number` — if 3 trailers genuinely share one number, that's a schema question, not just a
   display one.
3. **What triggers a new "job box" boundary vs. the same equipment just continuing?** E.g. if a
   piece of equipment goes straight from one job to the next with no yard stop, is that rendered
   as two adjacent boxes touching, or does the diagram ever show a single flow-through visual
   without a hard job/job boundary?
4. Confirm the arrival/departure split is always exactly two lists per job box (never three or
   more, e.g. for a job receiving equipment across two separate loads on different dates).

---

## 2. The auto-routing/load-design engine

### 2.1 Direct answers, verbatim from the owner (2026-08-03)

> We prefer to keep things on the road rather than unloading at the yard and reloading later.
> Storage is an option if something is a long way from the yard and it's not too long. But we
> rarely do that now. Perhaps we store a load for a few days.
>
> "spare capacity" — let's ignore this — it would be way too complicated to explain.
>
> Rules — I've given you the capacity calculations per lorry — we prefer Flatbeds.
>
> Distance = time = cost, which is why I spec'ed adding lat/long — we can roughly calculate cost
> and time between sites.
>
> Loads must ALWAYS arrive after crew, or there would be no-one to unload the trucks.
>
> Scope: as we add jobs to the planner — we should be able to get the planner to plan the whole
> season — all lorry moves. There will come a point where we need to "fix" certain loads, if
> they're very long or we've already booked the transport.
>
> It's very common to get jobs in late, so the planner needs to be aware of what's already
> happened in the year.
>
> E.g. — it's April — we're on the road — there's equipment all over Europe, and we get a job in
> for early June. We "think" we can do it, but the planner should re-plan loads after say, "a
> week's time", so we can see if the loads for the rest of the season make sense.
>
> The auto-planner is just that. We add jobs which have requirements in terms of dates and
> equipment. Press "auto-loads" (or something) and the app will design an efficient route for all
> equipment through the season taking distance/time into account.
>
> The output a "loads reviewer" should see is the loading diagram as discussed in 1. It should
> also generate the loading list (and in turn plonk the load numbers on the season planner on the
> right dates.)
>
> This might be a stretch — but we should have the option to add/remove equipment to/from a load
> manually.

### 2.2 What this means, mapped onto the existing model

- **Direct-move bias.** Prefer job → job moves over job → yard → job, matching D014's original
  V1 progression ("suggest direct movements" before "spare-capacity opportunities," which the
  owner has now said to skip entirely — see below). Yard storage is a fallback, used when a job is
  a long way from the yard and the wait would otherwise be short (days, not weeks).
- **Spare-capacity matching is explicitly out of scope** for this engine, at the owner's
  instruction — do not attempt to detect "this lorry already going that way has room for another
  job's gear" opportunistically. This simplifies the routing problem considerably: it's a
  direct/via-yard journey planner per equipment batch, not a bin-packing-across-jobs optimiser.
- **Lorry type preference: Flatbed over Curtainsider** when either would do, using the capacity
  math already recorded in `OPEN_QUESTIONS.md` Q042 (Flatbed 7.2 points / Curtainsider 6 points,
  points-per-section-type table). `Lorry`/`LorryType`/`Haulier` already exist in the schema
  (`app/models/administration.py`) — this is a preference to apply when choosing between available
  types, not new data.
- **Cost/time estimation from `Location.latitude`/`longitude`.** These fields exist specifically
  for this (D037's reseed geocoded every job venue). `RouteCache` (§7.29) and the routing-provider
  abstraction (D016) already exist in the schema/decisions but are unused — this is where they'd
  plug in. A rough straight-line/haversine estimate is a reasonable first cut; a real routing
  provider (D016) is a refinement, not a blocker.
- **Hard constraint: a load's arrival must never precede its receiving crew's arrival.** This maps
  onto the season board's already-implemented "receiving warning" conflict check
  (`app/services/conflicts.py`, D027/D031) and Q013 (can third parties receive loads) — the engine
  must respect this as a hard scheduling constraint, not just flag it after the fact.
- **Whole-season scope, re-plannable.** "Press auto-loads" should route every load for every job
  currently in the planner, not one job at a time — but it must be safe to re-run after the season
  is already underway and partly committed:
  - Respect `Load.locked`/`EquipmentMovement.locked` (already exist, D013) — a re-plan must never
    silently move a locked/committed load.
  - Respect what's already happened: actual movements in the past (or already in progress) are
    fixed history, not re-optimisable.
  - The owner's own framing suggests this is **not** a live/continuous optimiser — it's an
    explicit, planner-triggered action ("auto-loads" button), potentially re-run days after a
    late-arriving job is entered, giving the team a review window rather than instantly
    reshuffling the season the moment a job is added. This matches D014's original "assisted
    planning, not global optimisation" framing directly.
- **Output for the "loads reviewer":**
  1. The Loads Diagram (§1).
  2. A generated Loads List for hauliers (already modelled as `Load`/`LoadItem`; this is
     the engine actually populating them instead of a planner typing them by hand).
  3. Load numbers appearing on the season board on the correct dates — the season board already
     renders a load's arrive/depart as a stacked detail line inside the relevant job block
     (D038); this would just mean that line's load code is one the engine generated, not one a
     planner typed in manually.
- **Manual override (stretch goal, explicitly flagged as such by the owner):** ability to add or
  remove equipment from a specific load after auto-generation, without necessarily re-running the
  whole engine.

### 2.3 Crew-moves auto-planning (new, same conversation)

> While we're at it — the same sort of thing applies to crew. Jesse's crew moves from Job X to
> Yard or Job Y — may as well autofill crew moves too!

This extends the same idea to `CrewMovement`/`CrewJourneyLeg` (already modelled, currently entered
manually): when a Tentmaster's crew finishes one job (their Break phase ending, or an Up phase
handover) and starts the next, the engine should be able to auto-generate the crew movement
between the two — same underlying distance/time/date-window logic as the equipment engine, just
routing people instead of gear. Not fleshed out in detail yet; flagged here so it isn't lost, to
be designed properly alongside §2.2 rather than bolted on afterward.

---

## 3. Implementation notes (not decisions — things to remember when this gets built)

- Reinstate asset-code click-to-highlight in `board.js` (present before D038 removed the
  Equipment column; needed again for the Loads Diagram's "click K8, see its whole season" ask).
- `RouteCache`/routing-provider abstraction (D016, §7.29) is specified but unused anywhere in the
  codebase today — first real consumer would be this engine's cost/time estimation.
- The existing `Load.locked`/`EquipmentMovement.locked` fields are exactly the "fix certain loads"
  mechanism the owner described — no new schema needed for that part.
- `BuildStage`/`required_on_site_at`/`releasable_at` on `JobEquipmentRequirement` already define
  the date window each piece of equipment is needed within — the engine's job is to find lorries
  and routes that satisfy those windows across the whole season, not to invent new date logic.

---

## 4. Still to resolve before implementation can start

- §1.5's four open questions on the diagram's exact visual semantics.
- Whether "a week's time" (the re-plan review buffer) is a literal fixed delay, a manually
  triggered "re-plan now" action, or both (auto-suggest a re-plan after N days, planner confirms).
- Whether the engine is a single big optimisation pass or an incremental one (route each new job's
  equipment against the existing plan, vs. re-deriving the whole season fresh every run).
- Exact algorithm for choosing direct-vs-via-yard when a direct move is geographically awkward but
  not impossible (the owner ruled out "spare capacity" matching but a direct-move-preference still
  needs *some* tie-breaking rule for genuinely marginal cases).
