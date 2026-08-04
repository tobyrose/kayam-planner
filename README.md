# Kayam Seasonal Planning System

A local-first web application for planning Kayam’s seasonal tent-hire operations across time and
location. V1 coordinates jobs, modular equipment, crews, vehicles, loads, costs and feasibility
while preserving the continuous seasonal view used in the reference workbook.

## Current status

V1 milestones 1–12 are implemented as a runnable local-first planner:

- FastAPI with server-rendered Jinja templates
- SQLAlchemy 2.x session and declarative-base setup
- SQLite configuration and Alembic migrations
- A homepage, static asset shell, and `GET /health`
- Jobs, generated tent/component requirements and editable phases
- Named and placeholder crew assignments, availability checks and a crew board
- Soft/hard equipment allocation, compatibility, locking and asset timelines
- Equipment movements, numbered loads, multidimensional capacity and printable/CSV sheets
- Manual/OpenRouteService routing, route cache and transition feasibility margins
- Multi-leg crew movements with passenger/van capacity checks
- Estimated and actual costing, invoices, allocations and job margin summaries
- A synchronized seasonal board plus central conflict and assisted-suggestion views
- Automatic operational audit records, SQLite backup, JSON export and workbook diagnostics
- Pytest, Ruff, and mypy configuration
- CRUD administration for locations, tent/equipment definitions, crew reference data, vehicles and
  hauliers
- Configurable tent component requirements and date-based Tentmaster memberships
- Explicitly labelled, idempotent demonstration seed data

The implementation is a V1 planning baseline. Business constants still listed in
`OPEN_QUESTIONS.md` must be verified before production use.

**New to the project?** Read [`HANDOFF.md`](HANDOFF.md) first (what it does, what’s built, what’s
open, next priorities). Then `AGENTS.md` if you are coding.

## Requirements

- Python 3.12 or newer
- A terminal (Terminal on macOS/Linux, or PowerShell on Windows)
- Internet access during dependency installation and for the foundation page’s Bootstrap/HTMX CDN
  assets

SQLite is included with Python; no separate database server is required.

## Setup on macOS and Linux

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
```

If `python3.12` is not the command used by your installation, substitute the command that reports
Python 3.12 or newer when run with `--version`.

## Setup on Windows PowerShell

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m alembic upgrade head
```

If PowerShell blocks activation, either adjust the execution policy for the current process or run
the virtual-environment interpreter directly as `.\.venv\Scripts\python.exe`.

## Configuration

Configuration is loaded from environment variables and an optional `.env` file. Start by copying
`.env.example`; do not commit `.env` or real credentials.

The foundation settings are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Kayam Seasonal Planning System` | Display and API title |
| `APP_ENV` | `development` | Enables local development API docs |
| `KAYAM_DEBUG` | `false` | Enables framework and SQL debug output |
| `HOST` | `127.0.0.1` | Local bind address |
| `PORT` | `8000` | Local port |
| `DATABASE_URL` | `sqlite:///./instance/kayam.db` | SQLAlchemy database URL |
| `SECRET_KEY` | development placeholder | Reserved for later security features |
| `DEFAULT_TIMEZONE` | `Europe/London` | Default operational timezone |
| `ROUTING_PROVIDER` | `manual` | `manual` or `openrouteservice` |
| `OPENROUTESERVICE_API_KEY` | empty | Required only for OpenRouteService |
| `ROUTE_AMBER_MARGIN_MINUTES` | `360` | Below this transition margin is red |
| `ROUTE_GREEN_MARGIN_MINUTES` | `1440` | At or above this transition margin is green |

Keep `HOST=127.0.0.1` for normal local use. The SQLite database is created at
`instance/kayam.db` and is excluded from Git.

## Prepare the development database

Apply migrations directly:

```bash
python -m alembic upgrade head
```

Or run the idempotent development seed command, which first applies all migrations:

```bash
python -m app.commands.seed
```

The command inserts demonstration-only reference and planning data: Oxford Yard, configurable
Kayam tents, K1-style assets, four Tentmasters, crew, vehicles, three jobs, assignments, a load, a
multi-leg crew move and a sample cost allocation. It is idempotent and labels every placeholder;
review or replace all demonstration data before operational use.

## Run locally

Run with automatic reload:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Or use the local launcher, which reads `HOST`, `PORT`, and `APP_ENV`:

```bash
python run.py
```

Open <http://127.0.0.1:8000>. The health response is available at
<http://127.0.0.1:8000/health>; development API documentation is at
<http://127.0.0.1:8000/docs>. Core reference data is managed at
<http://127.0.0.1:8000/admin>. Start with the combined board at
<http://127.0.0.1:8000/planning> and the conflict centre at
<http://127.0.0.1:8000/conflicts>.

## Development checks

Run the complete test suite:

```bash
python -m pytest
```

Run linting and optional type checks:

```bash
python -m ruff check .
python -m mypy app
```

Verify that the migration history is current:

```bash
python -m alembic current
python -m alembic check
```

## Project structure

```text
app/
├── commands/       Local command-line utilities
├── models/         SQLAlchemy persistence models
├── repositories/   Database access
├── routes/         HTTP handling
├── schemas/        Request and business-data validation
├── services/       Transactions and cross-record administration rules
├── domain/         Routing and feasibility domain contracts
├── integrations/   External-provider adapters
├── static/         CSS and non-authoritative browser interactions
├── templates/      Server-rendered HTML
├── config.py       Environment-backed settings
├── database.py     SQLAlchemy engine and session lifecycle
└── main.py         FastAPI application assembly
migrations/         Alembic environment and revisions
tests/              Foundation and administration tests
instance/           Local SQLite data (not committed)
reference/          Reference workbooks, not live application data
```

The workbooks under `reference/` remain diagnostic references and are never the live datastore.

## Backup, export and restore

Create a consistent SQLite backup from the UI at `/system` or from the command line:

```bash
python -m app.commands.backup backups
python -m app.commands.export_json exports/kayam.json
```

To restore locally, stop the application, retain the current `instance/kayam.db` as a fallback,
copy the selected `.db` backup to `instance/kayam.db`, then run:

```bash
python -m alembic upgrade head
python -m pytest
```

Backups and exports may contain operational and personal data. Store them with access controls and
do not commit them.

## Workbook diagnostics

Inspect values, fills, merges, comments, and LD/CM notation without importing workbook data:

```bash
python -m app.commands.workbook_diagnostic "reference/DAILY V8.xlsx" \
  --output exports/daily-v8.diagnostic.json
```

## Hosted deployment guidance

The application defaults to `127.0.0.1` deliberately. Before exposing it on a network, add an
authentication/authorization layer, use a production secret, terminate TLS through a reverse
proxy, move to a managed PostgreSQL database after compatibility testing, run migrations as a
deployment step, and establish encrypted automated backups plus retention monitoring. A public
bind is not a supported production shortcut.

## Product principle

> Data is entered as jobs, requirements, assignments and movements, but users experience it as a
> continuous seasonal flow of people, equipment and transport.
