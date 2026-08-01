from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routes import (
    admin,
    board,
    conflicts,
    costing,
    crew_movements,
    crew_planning,
    equipment_planning,
    health,
    jobs,
    logistics,
    pages,
    routing,
    system,
)

APP_DIRECTORY = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url=None,
    )
    application.mount(
        "/static",
        StaticFiles(directory=APP_DIRECTORY / "static"),
        name="static",
    )
    application.include_router(pages.router)
    application.include_router(board.router)
    application.include_router(conflicts.router)
    application.include_router(admin.router)
    application.include_router(jobs.router)
    application.include_router(crew_planning.router)
    application.include_router(equipment_planning.router)
    application.include_router(logistics.router)
    application.include_router(routing.router)
    application.include_router(crew_movements.router)
    application.include_router(costing.router)
    application.include_router(system.router)
    application.include_router(health.router)
    return application


app = create_app()
