from __future__ import annotations

from typing import Literal, TypedDict

from fastapi import APIRouter

router = APIRouter(tags=["health"])


class HealthResponse(TypedDict):
    status: Literal["ok"]


@router.get("/health")
def health_check() -> HealthResponse:
    """Return a lightweight process-health response."""

    return {"status": "ok"}
