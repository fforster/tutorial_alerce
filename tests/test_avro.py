"""Tests for the AVRO record metadata viewer service."""
from __future__ import annotations

import asyncio

from src.services import alerce_client
from src.services import avro as avro_service


def _run(coro):
    return asyncio.run(coro)


def test_lsst_returns_unavailable_without_upstream_call(monkeypatch):
    """LSST has no AVRO equivalent on the public API. The service must
    short-circuit before hitting upstream so we don't spam 404s — and so
    the modal can render an explanatory message."""
    called = False

    async def fake_get(url):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(alerce_client, "_get", fake_get)
    out = _run(avro_service.get_avro_info(
        oid="313888627082919999", candid="abc", survey="lsst",
    ))
    assert out["available"] is False
    assert "LSST" in out["reason"]
    assert out["rows"] == []
    assert not called, "service shouldn't fetch upstream for non-ZTF"


def test_ztf_shapes_candidate_block_into_sorted_rows(monkeypatch):
    async def fake_get(url):
        # Sanity: the URL points at the ALeRCE AVRO proxy with the
        # right oid/candid.
        assert "avro.alerce.online/get_avro_info" in url
        assert "oid=ZTF17aabhbva" in url
        assert "candid=740463761015010003" in url
        return {
            "candidate": {
                "magpsf": 20.247024536132812,
                "drb": 0.0,
                "isdiffpos": "f",
                "rb": True,
                "fid": 1,
                "missing_thing": None,
                "weird_nan": float("nan"),
            },
            "objectId": "ZTF17aabhbva",
            "publisher": "ALeRCE",
            "schemavsn": "3.3",
            "prv_candidates": [{}, {}, {}],
        }

    monkeypatch.setattr(alerce_client, "_get", fake_get)
    out = _run(avro_service.get_avro_info(
        oid="ZTF17aabhbva", candid="740463761015010003", survey="ztf",
    ))
    assert out["available"] is True
    assert out["object_id"] == "ZTF17aabhbva"
    assert out["publisher"] == "ALeRCE"
    assert out["schemavsn"] == "3.3"
    assert out["n_prv_candidates"] == 3
    # Rows are sorted by name (deterministic for snapshot tests).
    names = [r["name"] for r in out["rows"]]
    assert names == sorted(names)
    by_name = {r["name"]: r for r in out["rows"]}
    # Float formatting (~7 sig figs) — picks up magpsf via the 7g format.
    assert by_name["magpsf"]["value_display"].startswith("20.247")
    # NaN renders as empty (not "nan" verbatim).
    assert by_name["weird_nan"]["value_display"] == ""
    # Booleans normalize to lowercase.
    assert by_name["rb"]["value_display"] == "true"
    # None → empty string.
    assert by_name["missing_thing"]["value_display"] == ""


def test_upstream_error_surfaces_as_unavailable(monkeypatch):
    async def fake_get(url):
        raise RuntimeError("avro endpoint down")

    monkeypatch.setattr(alerce_client, "_get", fake_get)
    out = _run(avro_service.get_avro_info(
        oid="ZTF17aabhbva", candid="x", survey="ztf",
    ))
    assert out["available"] is False
    assert "Upstream error" in out["reason"]
    assert out["rows"] == []


def test_missing_candidate_block_surfaces_as_unavailable(monkeypatch):
    async def fake_get(url):
        return {"objectId": "ZTF17aabhbva", "publisher": "ALeRCE"}

    monkeypatch.setattr(alerce_client, "_get", fake_get)
    out = _run(avro_service.get_avro_info(
        oid="ZTF17aabhbva", candid="x", survey="ztf",
    ))
    assert out["available"] is False
    assert "candidate" in out["reason"].lower()
    # Even on the empty path, meta fields ride through so the modal
    # header can still show schemavsn / publisher when present.
    assert out["object_id"] == "ZTF17aabhbva"
    assert out["publisher"] == "ALeRCE"


def test_non_dict_response_surfaces_as_unavailable(monkeypatch):
    async def fake_get(url):
        return ["not", "a", "dict"]

    monkeypatch.setattr(alerce_client, "_get", fake_get)
    out = _run(avro_service.get_avro_info(
        oid="ZTF17aabhbva", candid="x", survey="ztf",
    ))
    assert out["available"] is False
