"""htmx endpoints — return HTML fragments via Jinja2.

Slice 1 ships stub partials so the full routing shell is runnable; Slice 2
will replace them with real search/filter logic that calls the ALeRCE API.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

router = APIRouter()

templates = Jinja2Templates(directory=str(TEMPLATES_DIR), autoescape=True, auto_reload=True)
templates.env.globals["API_URL"] = os.getenv("API_URL", "http://localhost:8000")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html.jinja", {"request": request})


@router.get("/htmx/search_objects/", response_class=HTMLResponse)
async def search_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "search_form/form.html.jinja",
        {"request": request, "classifiers": []},
    )


@router.get("/htmx/classes_select", response_class=HTMLResponse)
async def classes_select(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "search_form/dependent_select.html.jinja",
        {"request": request, "classes": []},
    )


@router.get("/htmx/list_objects", response_class=HTMLResponse)
async def list_objects(request: Request) -> HTMLResponse:
    empty = {
        "items": [],
        "current_page": 1,
        "has_prev": False,
        "prev": False,
        "has_next": False,
        "next": False,
        "info_message": "Slice 1: results wiring comes in the next slice.",
    }
    return templates.TemplateResponse(
        "main_table_objects/objects_table.html.jinja",
        {"request": request, "objects_list": empty},
    )


@router.get("/htmx/object_information", response_class=HTMLResponse)
async def object_information(request: Request, oid: str, survey_id: str) -> HTMLResponse:
    return templates.TemplateResponse(
        "basic_information/basicInformationPreview.html.jinja",
        {"request": request, "oid": oid, "survey_id": survey_id},
    )
