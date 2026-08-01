from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.main_paths import TEMPLATE_DIRECTORY

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)


@router.get("/", response_class=HTMLResponse)
def homepage(request: Request) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"app_name": settings.app_name},
    )
