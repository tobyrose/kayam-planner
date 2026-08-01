from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.crew_movements import CrewMovement
from app.models.logistics import Load


def test_operational_pages_render_with_showcase_data(session: Session, client: TestClient) -> None:
    seed_development_data(session, include_operational_demo=True)
    load = session.scalar(select(Load))
    crew_move = session.scalar(select(CrewMovement))
    assert load is not None and crew_move is not None
    paths = (
        "/planning?start=2026-06-01&end=2026-08-31",
        "/conflicts",
        "/loads",
        f"/loads/{load.id}",
        "/routes",
        "/crew-moves",
        f"/crew-moves/{crew_move.id}",
        "/costs",
        "/system",
        "/system/export.json",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
