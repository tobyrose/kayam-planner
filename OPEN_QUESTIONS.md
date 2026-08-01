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

## Q001 — What precisely is a Tentmaster?

**Status:** Open  
**Needed by:** Crew administration and crew-board implementation  
**Question:** Is a Tentmaster primarily a team, the lead person, or both?

**Current assumption:** Model Tentmaster as a working team with an optional lead crew member.

---

## Q002 — Which tent families and configurations exist?

**Status:** Open  
**Needed by:** Production seed data  
**Question:** What are the complete tent families, sizes and component templates?

**Current assumption:** Seed Kayam 4-, 6-, 10- and 12-pole examples only.

---

## Q003 — What equipment is compatible?

**Status:** Open  
**Needed by:** Equipment suggestion engine  
**Question:** Which ends, middles, poles and ancillary items can be combined across variants or tent families?

**Current assumption:** Exact equipment type match unless an explicit compatibility record says otherwise.

---

## Q004 — How are poles tracked?

**Status:** Open  
**Needed by:** Equipment model  
**Question:** Are poles individually numbered, grouped into bundles, or treated as quantities?

**Current assumption:** Support either through configurable tracking mode.

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

**Status:** Open  
**Needed by:** Production labour costing  
**Question:** Confirm hourly rate, overtime, travel pay, daily allowance and any minimum-day rules.

**Current assumption:** Configurable simple rates with manual adjustments; no payroll.

---

## Q012 — How should travel cost be allocated between jobs?

**Status:** Open  
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

## Q015 — May one job have several simultaneous Tentmasters?

**Status:** Open  
**Needed by:** Job phases and board  
**Question:** Can separate tents or phases at one job be handled by independent teams?

**Current assumption:** Yes. Assign Tentmasters at phase level, not only job level.

---

## Q016 — How should local crew be represented?

**Status:** Open  
**Needed by:** Crew planning  
**Question:** Are local crew tracked by names, supplier, headcount only, or a mixture?

**Current assumption:** Allow named crew and placeholders such as `Local crew × 4`.

---

## Q017 — How is maintenance cover represented?

**Status:** Open  
**Needed by:** Job phases  
**Question:** Does maintenance cover reserve a minimum crew continuously, at specified windows, or on call?

**Current assumption:** Use explicit maintenance phases and required headcount.

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

**Status:** Open  
**Needed by:** Transport estimates  
**Question:** Are prices based on route, mileage, minimum charge, number of days, ferry, waiting or negotiated quote?

**Current assumption:** Support manual estimates and configurable rate-card formulas.

---

## Q021 — Is VAT required for invoice tracking?

**Status:** Open  
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

## Q036 — Can Tentmaster membership change during a day?

**Status:** Open  
**Needed by:** Crew administration and later crew scheduling  
**Question:** May a crew member finish with one Tentmaster and join another on the same calendar
date, and if so must the handover be recorded at a specific time?

**Current assumption:** Membership start and end dates are inclusive, so same-date membership
boundaries overlap and are rejected. Use consecutive dates until the operational rule is confirmed.

---

## Q037 — How long must audit and backup data be retained?

**Status:** Open  
**Needed by:** Production operations and privacy policy  
**Question:** What retention, deletion and access-control rules apply to audit records, database
backups and JSON exports containing staff or supplier information?

**Current assumption:** Retain audit records indefinitely in local V1 and leave backup retention to
the planner. Define an encrypted automated retention policy before hosted deployment.
