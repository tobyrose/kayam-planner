# AGENTS.md

## Purpose

This repository contains the Kayam Seasonal Planning System: a time-and-space-aware planning application for modular tent equipment, crews, vehicles, haulage and seasonal events.

Before making architectural or business-rule changes, read:

1. `HANDOFF.md` — short orientation: what the app does, built vs open, next-session priorities
2. `SPECIFICATION.md`
3. `DECISIONS.md`
4. `OPEN_QUESTIONS.md`
5. `IMPLEMENTATION_PLAN.md`
6. `LOAD_ENGINE_DESIGN.md` — design notes for the automatic load-design/routing engine and Loads
   Diagram (V1 engine + diagram shipped; further optimisation still design/open)

Treat `SPECIFICATION.md` as the primary product source of truth. For “where are we?”, start with
`HANDOFF.md`.

## Core working rules

1. Keep the application runnable after every completed task.
2. Work through `IMPLEMENTATION_PLAN.md` in order unless the user explicitly changes priorities.
3. Do not silently break completed milestones while implementing later work.
4. Add or update tests for every business-rule change.
5. Use Alembic migrations for all database schema changes.
6. Never commit secrets, API keys, passwords or production credentials.
7. Preserve planner locks and manually approved assignments.
8. Never silently move, replace or unassign confirmed operational resources.
9. Keep scheduling, costing and feasibility calculations in Python services, not templates or browser JavaScript.
10. Prefer clear, maintainable code over premature abstraction.
11. Record architectural choices in `DECISIONS.md`.
12. Record unresolved business questions in `OPEN_QUESTIONS.md`.
13. Do not invent production business data.
14. Use `reference/DAILY V8.xlsx` only as a reference unless an import task explicitly requests otherwise.
15. Run the relevant test suite before marking work complete.
16. If a requirement is ambiguous, use the safest reversible assumption and record it.
17. Suggested plans must remain distinguishable from approved or locked plans.
18. Confirmed work must take precedence over provisional work unless a planner explicitly overrides it.
19. Avoid hard-coding Oxford-specific behaviour; model Oxford Yard as a normal location of type `yard`.
20. Avoid hard-coding tent composition rules; use configurable tent templates and component requirements.

## Preferred architecture

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- SQLite initially
- Jinja2
- HTMX
- Vanilla JavaScript for planning-board interaction
- Bootstrap 5 or a similarly lightweight CSS framework
- pytest
- Pydantic settings
- OpenRouteService behind a provider interface
- Manual routing fallback

Do not introduce React or another separate frontend application without first documenting why the existing architecture cannot satisfy the requirement.

## Layering

- `routes/`: HTTP handling and request validation
- `schemas/`: request/response validation
- `repositories/`: database access
- `services/`: business operations and transactions
- `domain/`: scheduling, feasibility, capacity and costing rules
- `integrations/`: routing and other external providers
- `templates/`: rendering only
- `static/`: CSS and browser interaction only

JavaScript must not become the authoritative source of scheduling state or rules.

## Data integrity

Use transactions for operations that update multiple related records.

Examples:

- Confirming a job and converting approved soft allocations to hard allocations
- Assigning equipment and creating related movement requirements
- Adding load contents and recalculating capacity
- Moving a crew member between assignments
- Recording an invoice and allocating its cost

If an operation fails, avoid partial updates.

## Scheduling invariants

At minimum, preserve these invariants:

- A physical equipment asset cannot have overlapping hard assignments.
- A named crew member cannot have overlapping confirmed assignments.
- Locked assignments survive automatic recalculation.
- A suggested plan never becomes committed without explicit approval.
- A load cannot silently exceed known capacity.
- An asset journey must maintain location continuity.
- A confirmed job must not silently displace another confirmed job.
- Provisional conflicts should warn rather than always block.
- Direct travel feasibility must include loading, operational travel and unloading time.
- Route API driving time and operational planning time are separate values.

## Testing expectations

At minimum, add tests for:

- Tent requirement expansion
- Date validation
- Equipment compatibility
- Hard and soft conflicts
- Travel feasibility
- Load capacity
- Crew overlap
- Lock preservation
- Cost estimates
- Margin calculations
- Route caching
- Confirmation workflow
- Asset location continuity

Suggested commands:

```bash
python -m pytest
python -m ruff check .
python -m mypy app
alembic upgrade head
```

Use Ruff and mypy when configured. Do not block early milestones on exhaustive type coverage.

## Documentation expectations

Update documentation when behaviour changes.

- `README.md`: installation and operational usage
- `DECISIONS.md`: important architecture and product decisions
- `OPEN_QUESTIONS.md`: unresolved matters
- `IMPLEMENTATION_PLAN.md`: progress and task status
- `SPECIFICATION.md`: only when the agreed product specification changes

Do not rewrite the specification merely to match an implementation shortcut.

## Completion report

When completing a task, report:

- What changed
- Which files changed
- Migrations created
- Tests added or updated
- Commands run
- Known limitations
- Any new decision or open question
