"""Thin httpx client for the ALeRCE public REST API.

Slice 1 just declares the shape — the table/detail slices will call these.
"""
from __future__ import annotations

from typing import Any

import httpx

from .safe_json import safe_json_loads
from .survey_config import SC


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=15.0)


async def list_objects(survey: str, params: dict[str, Any]) -> dict[str, Any]:
    cfg = SC(survey)
    query = cfg.extra_params({**params, "survey": survey})
    async with _client() as client:
        r = await client.get(f"{cfg.api_base}/objects", params=query)
        r.raise_for_status()
        return safe_json_loads(r.content)


async def get_object(survey: str, oid: str) -> dict[str, Any]:
    cfg = SC(survey)
    async with _client() as client:
        r = await client.get(f"{cfg.api_base}/objects/{oid}")
        r.raise_for_status()
        return safe_json_loads(r.content)


async def get_classifiers(survey: str) -> dict[str, Any]:
    cfg = SC(survey)
    async with _client() as client:
        r = await client.get(f"{cfg.api_base}/classifiers")
        r.raise_for_status()
        return safe_json_loads(r.content)
