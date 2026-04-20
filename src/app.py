"""FastAPI entrypoint.

Single-app layout (tutorial). Production ALeRCE splits each feature into its
own service; for this tutorial we mount everything under one app.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import htmx, rest

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Tutorial ALeRCE Explorer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.api_url = os.getenv("API_URL", "http://localhost:8000")

app.include_router(htmx.router)
app.include_router(rest.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
