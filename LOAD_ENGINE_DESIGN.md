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
sections or 'magic' things to places." Three reference images were supplied and read directly:

- `reference/kay_loads_diagram.png` — a full season, hand-built in Excel.
- `reference/kay.loads.close.example.png` — a hand-drawn close-up of one small section of the
  same idea, walked through verbally.
- `reference/kay.loads.valhalla.example.png` — a second full-season snapshot (Valhalla family),
  supplied to walk through the Roskilde → New Day → Reading worked example in §1.3.

What follows is my read of those images plus the owner's explanation, written out in full so it
can be checked rather than assumed correct. §1.2's structure and §1.5's four open questions were
fully resolved by the owner on 2026-08-04 — read those sections for current understanding.

### 1.2 Structure — resolved 2026-08-04, all four §1.5 open questions answered

- **Dates run down the left**, one row per day — same convention as the season board and the
  existing `/planning/flow` diagram.
- **Job columns are dynamically packed, not fixed lanes.** A job's column spans from its **first
  Build day to its last Break day** (exactly `_job_window()` in `app/services/board.py` — no new
  date logic needed, just reuse it) — the same "expand columns as needed, shrink when not"
  interval-packing idea already built for the season board's Unassigned/Quoted lane (D038),
  confirmed by the owner as the right model here too. Boxes **do not need to touch** each other —
  gaps between a job's column and whatever's in that column-slot next represent travel time. Think
  of the whole diagram as a graph of how sections move over time, not a floor plan.
- **The Yard is one fixed column, always present — not dynamically packed, and not showing its
  full contents by default.** This resolves what was originally thought to be the hardest part of
  the diagram: the owner confirmed the *position* of the Yard block in the original hand-built
  sheet was never meaningful ("for sure wherever Excel happened to have a free column that
  week... the position and size of YARD block is irrelevant compared to date loads go in and out
  of Yard, which should be on the correct date"). So instead of trying to reproduce that
  positioning, the Yard becomes a normal single column like everything else in `/planning/flow`
  today: **it shows only load-number markers on the dates loads depart or arrive** (e.g. "load 1,
  2, 3 depart" / "load 4, 5, 6 arrive"), not a running list of every component sitting there.
  Clicking a date in the Yard column opens the existing side-panel pattern (the one job blocks
  already open, D038) as a **slide-out showing exactly what's in the Yard that day** — incoming
  and outgoing components each coloured to match the job/load they're connected to. Full detail is
  a click away rather than permanently on-screen, which is both truer to what the owner actually
  cares about (dates in/out, not a permanent live inventory snapshot) and removes the hardest
  layout problem entirely.
- **A job's box lists real equipment codes, not just a section-sequence summary**, in exactly two
  stacked lists: an **arrivals list on top, a departures list below** — the same items repeated in
  the "going out" list when they leave, per the owner: "components should be shown 'coming in' to
  a job, components are repeated below the dividing line where they 'go out' of the job." Neither
  list is limited to one same-day/same-origin batch — **a job can receive loads from several
  different origins on several different dates, and send loads to several different destinations
  on several different dates**, all listed within that one job's box, positioned against the
  correct date rows. Confirmed directly against a second worked example (§1.3): New Day's box
  shows incoming loads from *both* Roskilde and the Yard; Reading's box shows incoming loads from
  *both* New Day and the Yard.
- **Colour marks provenance/destination, not job identity** — a batch of equipment travelling
  together keeps one colour from its origin box's departure list through to its destination box's
  arrival list, which is what lets a planner trace "what's leaving, what's arriving, where it's
  going" at a glance.
- **One load number = one load = one lorry — always.** This resolves the "8 8 8" ambiguity: it is
  **not** three trailers sharing one number. It's a single load (load 8) whose number is shown
  more than once as a positional/visual aid — appearing near its departure point and again near
  its arrival point as the diagram's layout moves it "left to free space, then down to another
  job." The existing `Load` model (one row per lorry, its own `load_number`) needs no schema
  change for this. Where a job genuinely needs multiple lorries (e.g. Silverstone's "15, 16, 17"),
  that's exactly what it looks like: multiple *distinct* sequential numbers, one per lorry, per
  the points-per-lorry capacity math in `OPEN_QUESTIONS.md` Q042.
- **Clicking an equipment code should trace it through the whole season.** Owner's example:
  **"we could click on K8 for example — it would highlight and we could track exactly how that
  section flows through the season."** This is the same click-to-highlight interaction the season
  board already has for jobs (D033) and that the flow diagram/board.js used to have for individual
  assets before the season-board rebuild dropped the separate Equipment column (D038) — it needs
  to come back specifically for this diagram (see §3, implementation note).

### 1.3 Worked examples, verbatim from the owner

**Yard → Silverstone** (single direct move, multi-lorry):

> Taking Yard to Silverstone as an example: these places are quite close, we load on 18th June —
> arrive 19th June. Load 15, 16, 17 contains all equipment we need for Silverstone — so split of
> things will be up to the Tentmaster. Critically — the things we need at Silverstone adds up to
> 3 trailers — so that's what we show. We show all the sections coming in (in purple here) line —
> copy all the things underneath in the same box and show them going out.

**Roskilde → New Day → Reading, plus Yard top-ups** (multi-origin arrivals, `reference/kay.loads.valhalla.example.png`, a Valhalla-family snapshot):

> Load 12, 13, 14 goes from Roskilde to New Day. Load 25, 26 go from the Yard to New Day. Load 44,
> 45, 46, 47, 48 go from New Day to Reading. Load 49 goes from the Yard to Reading. Everything is
> shown on the right dates.

New Day's box therefore shows two separate incoming groups (Roskilde's 12/13/14 and the Yard's
25/26) in its arrivals list; Reading's box shows two separate incoming groups (New Day's
44–48 and the Yard's 49) in its arrivals list — directly confirming the "arrivals/departures can
each span several origins and dates" rule above.

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
- The Yard turned out to need no special packing at all once resolved (§1.2) — it's one fixed
  column like any other location column in `/planning/flow` today, not a dynamically-packed or
  recurring one. That removes what looked like the one genuinely hard rendering problem.
- `AGENTS.md`'s own rule — JavaScript stays presentational, structured records drive everything —
  argues against introducing a heavy client-side data-viz framework for something a template loop
  can already produce. It would also be the first non-vanilla-JS dependency in the stack
  (FastAPI + Jinja2 + HTMX + vanilla JS today).
- Fallback: if, once built, some other part of the layout genuinely can't read clearly in a strict
  table grid, the SVG-overlay technique already used for flow-diagram journey lines can be
  extended rather than reaching for D3 wholesale.

### 1.5 Open questions on the diagram itself — RESOLVED 2026-08-04

1. **How does the Yard get its column(s)?** Resolved: it doesn't need dynamic packing — it's one
   fixed column, always present. The original sheet's Yard block position/size was confirmed
   meaningless ("wherever Excel happened to have a free column that week"). Instead of full
   contents, the column shows only load-number markers on move dates, with a click-to-expand
   side-panel (reusing the existing job-block panel pattern, D038) showing that day's full
   in/out detail with matching colours. See §1.2.
2. **Load-number header semantics.** Resolved: one number is always one load is always one lorry.
   A repeated number (the "8 8 8" case) is the *same* load shown at more than one point along its
   path as a visual/positional aid, not multiple trailers sharing a number — no schema change
   needed. Distinct sequential numbers (e.g. "15, 16, 17") mean genuinely distinct lorries. See
   §1.2 and §1.3.
3. **What triggers a new "job box" boundary?** Resolved: a job's box spans first Build day to last
   Break day (`_job_window()`, already implemented). Boxes don't need to touch — gaps are travel
   time, and the diagram is a graph of movement over time, not a floor plan. See §1.2.
4. **Is the arrival/departure split always exactly two lists?** Resolved: yes, always exactly two
   (arrivals on top, departures below, mirrored) — but either list can span multiple origins/
   destinations and multiple dates within it, not just one same-day batch. Confirmed directly
   against the Roskilde/Yard → New Day → Reading/Yard worked example in §1.3.

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

The diagram's own visual semantics (§1.5) are now fully resolved. What's left is entirely about
the routing engine itself:

- Whether "a week's time" (the re-plan review buffer) is a literal fixed delay, a manually
  triggered "re-plan now" action, or both (auto-suggest a re-plan after N days, planner confirms).
- Whether the engine is a single big optimisation pass or an incremental one (route each new job's
  equipment against the existing plan, vs. re-deriving the whole season fresh every run).
- Exact algorithm for choosing direct-vs-via-yard when a direct move is geographically awkward but
  not impossible (the owner ruled out "spare capacity" matching but a direct-move-preference still
  needs *some* tie-breaking rule for genuinely marginal cases).

With the diagram's design settled, the Loads Diagram itself (§1) could reasonably move to
implementation next, ahead of the routing engine (§2) — it's a read/visualisation feature over
already-existing `Load`/`EquipmentMovement`/`JobEquipmentRequirement` data (once loads exist to
show), with no open design questions left, unlike §2 which still has real unresolved algorithm
choices above.
