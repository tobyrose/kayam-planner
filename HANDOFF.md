# HANDOFF.md — Kayam Seasonal Planning System

**Purpose:** One place for a new human or agent to learn what this app is, what is built,
what is still open, and what to do next. Prefer this over chat history.

**Last updated:** 2026-08-04

---

## 1. What the app does

Kayam hires modular tents for seasonal events. This repo is a **local-first seasonal planner**
that coordinates:

| Area | What it covers |
| --- | --- |
| **Jobs** | Events with tent sequences, contract Up/Down, Build / Up / Break phases |
| **Equipment** | Sections, poles, linked kit; soft/hard assignment; locks |
| **Crew** | Tentmasters, roster membership, phases, local crew, crew moves |
| **Logistics** | Equipment movements, numbered loads (`L#`), Flat/Curtain capacity |
| **Season board** | `/planning` — dates down, Tentmasters across, continuous job bars |
| **Loads diagram** | `/planning/flow` — continuous job blocks, Yard column, load arrows |
| **Season generate** | Button on `/loads` — auto section/pole loads, job→job, return-to-Yard, crew moves |
| **Also** | Conflicts, costing/invoices, routing cache, admin CRUD, seed/reseed |

**Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, SQLite, Jinja2, HTMX, vanilla JS,
Bootstrap. **No React SPA** unless documented first (`AGENTS.md`).

**Domain principle:** Scheduling, capacity and costing live in **Python services**, not browser JS.
Planner **locks** must be preserved. Suggested/auto plans stay distinguishable from confirmed work.

---

## 2. Read order (always)

1. `AGENTS.md` — working rules  
2. `SPECIFICATION.md` — product source of truth  
3. `DECISIONS.md` — architecture choices (see D043–D044 for board + season loads)  
4. `OPEN_QUESTIONS.md` — unresolved business questions  
5. `IMPLEMENTATION_PLAN.md` — milestones + **“Next session — follow-ups”**  
6. `LOAD_ENGINE_DESIGN.md` — loads diagram / auto-routing design notes  
7. `README.md` — install and run  

If something conflicts, **SPECIFICATION** wins for product intent; record deviations in
**DECISIONS** / **OPEN_QUESTIONS**, do not silently rewrite the spec.

---

## 3. What is already built (high level)

### Core V1
- Jobs, tent expansion, phases, equipment requirements and assignments  
- Crew/Tentmaster model, roster board, crew movements  
- Movements, loads, capacity, printable load sheets  
- Season board, conflicts, costing, audit/backup/export  
- Admin for locations, equipment types, vehicles, hauliers  

### Recent (season loads / boards — 2026-08)
- **Season board:** continuous multi-day bars, packed unassigned columns, wall-clock forms,
  UP labels only on contract days, kit shortfall dots, job side panel with **inbound/outbound loads**  
- **Loads diagram (`/planning/flow`):** continuous job overlays, contract **Up** colour band,
  arrivals top / departures bottom, convoy arrows (`L18–L21`), Yard out/in + day stock click  
- **Season plan V1** (`app/services/season_plan.py`):  
  - Packs **sections + poles** (linked kit expanded on sheets, not free-pooled)  
  - Prefer **job→job**, else Yard → job  
  - **Leave at contract Down** (not just-in-time for next Build); early arrival OK  
  - **Return leftover free stock to Yard** after last use  
  - Optional **auto crew moves** between consecutive Tentmaster visits at different sites  
  - Regen clears **unlocked** auto loads/crew moves only; **locked** plans kept  

Key code: `app/services/season_plan.py`, `app/services/flow.py`, `app/services/board.py`,
`app/services/section_coverage.py`, `app/time_display.py`.

---

## 4. Questions still open (do not invent answers)

Full list: **`OPEN_QUESTIONS.md`**. Highest priority for the next session:

| ID | Topic | Notes |
| --- | --- | --- |
| **Q043** | Ancillary kit (e.g. stake basher) through the season | **Does not auto-track today.** Only sections/poles in free pool. Regen wipes unlocked auto loads. Options: lock-on-edit / carry-ancillaries / job-level requirements. |
| **Q044** | Auto crew-move generator | **Verify in practice** what legs/dates/modes it creates; confirm vs planner expectations. |
| **Q042** | Lorry points (Curtain 6 / Flat 7.2, Kayam points table) | Data recorded; Valhalla packing / SC points still need care. |
| Older Qs | Pay, VAT, route margins, permissions, host DB, etc. | Scan `OPEN_QUESTIONS.md`; many are production-readiness, not day-1 UI blockers. |

---

## 5. What is left to develop

### Next session (parked — see also `IMPLEMENTATION_PLAN.md`)

1. **Q043** — decide product behaviour for ancillaries, then implement  
2. Optional: warn when editing an unlocked auto load that regen will replace it  
3. **Q044** — review auto crew moves end-to-end; document or fix gaps  

### Medium term (design / roadmap)

- Richer load optimiser: spare-capacity hitchhiking, multi-leg via-yard, named assets  
- Better road distances (ORS provider exists; haversine used in season gen V1)  
- Loads diagram / season board polish with owner feedback  
- Production: auth, real constants, hosted DB, exports matching existing sheets  

`LOAD_ENGINE_DESIGN.md` remains the design conversation for automatic load design beyond V1.

---

## 6. Critical current behaviours (gotchas)

1. **Regen is destructive for unlocked auto plans.** Manual edits on unlocked generated loads
   (including a stake basher) are **lost** when you re-run generate unless the load/movement is
   **locked**.  
2. **Ancillaries do not ride the free pool.** Job→job and Yard-return only rebalance section/pole
   quantities, not “everything that was on L12”.  
3. **Leave-at-break:** job→job leaves near donor contract Down; kit may sit early at the next site.  
4. **Return-to-Yard:** leftover free stock after the last job becomes site → Yard loads.  
5. **Oxford Yard** is a normal `yard` location — do not hard-code Oxford-specific rules.  
6. **Do not invent production business data.** Reference workbooks under `reference/` are
   reference unless an import/reseed task explicitly uses them.

---

## 7. Setup & verify

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env               # Windows: Copy-Item .env.example .env
python -m alembic upgrade head
python -m pytest
```

Run the app as documented in `README.md`. SQLite is typically `instance/kayam.db` (local data;
may or may not be in git).

Useful UI paths:

- `/planning` — season board  
- `/planning/flow` — loads diagram  
- `/loads` — load list + **Generate season loads & crew moves**  
- `/jobs/{id}` — job detail (loads section); side panel uses `/jobs/{id}/summary`

---

## 8. How to work in this repo

- Keep the app runnable after every completed task  
- Prefer small, reversible changes; record decisions and open questions  
- Tests for business-rule changes; Alembic for schema  
- UI: server-rendered + HTMX/JS for interaction only  
- When the owner’s rule is unclear: safest reversible assumption + note in `OPEN_QUESTIONS.md`

---

## 9. Suggested first message for a new agent/person

After they have the repo and have (or will) read this file:

```text
Read HANDOFF.md end-to-end, then AGENTS.md.

Summarise in plain language:
1) what the app does,
2) what is already built for season loads / boards,
3) open questions Q043 and Q044 and why they matter,
4) the three next-session follow-ups.

Do not start large features until I prioritise. Propose the single smallest useful next change.
```

Shorter variant:

```text
Summarise HANDOFF.md: product purpose, built vs not built, open Q043/Q044, next session tasks.
Wait for priority before coding.
```
