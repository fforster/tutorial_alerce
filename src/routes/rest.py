"""JSON endpoints — used for programmatic clients and for the client-side JS
features (Chart.js, FITS, Aladin) that need data rather than HTML fragments.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["rest"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
