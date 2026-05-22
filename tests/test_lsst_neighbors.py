"""Tests for the LSST-neighbours cone-search service.

We don't exercise the HTTP client here — `filter_neighbors` is pure and
covers the time-window, exclude-oid, and missing-field branches without
needing to monkeypatch alerce_client.
"""
from __future__ import annotations

from src.services.lsst_neighbors import (
    LSST_NEIGHBORS_LASTMJD_WINDOW,
    filter_neighbors,
)


def _row(oid, ra, dec, lastmjd):
    return {"oid": oid, "meanra": ra, "meandec": dec, "lastmjd": lastmjd}


def test_filter_neighbors_keeps_rows_inside_window():
    items = [
        _row("111", 180.0, -30.0, 60000.0),
        _row("222", 180.1, -30.0, 60000.0 + LSST_NEIGHBORS_LASTMJD_WINDOW),
        _row("333", 180.2, -30.0, 60000.0 - LSST_NEIGHBORS_LASTMJD_WINDOW),
    ]
    out = filter_neighbors(items, lastmjd=60000.0)
    assert [r["oid"] for r in out] == ["111", "222", "333"]
    assert out[0] == {"oid": "111", "ra": 180.0, "dec": -30.0, "lastmjd": 60000.0}


def test_filter_neighbors_drops_rows_outside_window():
    items = [
        _row("inside", 180.0, -30.0, 60000.0),
        _row("after", 180.0, -30.0, 60000.0 + LSST_NEIGHBORS_LASTMJD_WINDOW + 0.01),
        _row("before", 180.0, -30.0, 60000.0 - LSST_NEIGHBORS_LASTMJD_WINDOW - 0.01),
    ]
    out = filter_neighbors(items, lastmjd=60000.0)
    assert [r["oid"] for r in out] == ["inside"]


def test_filter_neighbors_excludes_self_oid():
    items = [
        _row(123456789012345678, 180.0, -30.0, 60000.0),
        _row(987654321098765432, 180.0, -30.0, 60000.0),
    ]
    out = filter_neighbors(items, lastmjd=60000.0, exclude_oid="123456789012345678")
    assert [r["oid"] for r in out] == ["987654321098765432"]


def test_filter_neighbors_stringifies_int_oids():
    """LSST OIDs are 64-bit ints; the JSON layer feeds them through as ints
    (safe_json wraps them as strings, but tests pass dicts directly, so we
    cover both)."""
    items = [_row(313888627082919999, 180.0, -30.0, 60000.0)]
    out = filter_neighbors(items, lastmjd=60000.0)
    assert out[0]["oid"] == "313888627082919999"


def test_filter_neighbors_dedupes_repeated_oids():
    """Upstream list_objects returns each object once per classifier listing,
    so the same oid often appears twice. The filter keeps only the first."""
    items = [
        _row("dup", 180.0, -30.0, 60000.0),
        _row("dup", 180.0, -30.0, 60000.0),
        _row("other", 180.01, -30.01, 60000.0),
        _row("dup", 180.0, -30.0, 60000.0),
    ]
    out = filter_neighbors(items, lastmjd=60000.0)
    assert [r["oid"] for r in out] == ["dup", "other"]


def test_filter_neighbors_skips_rows_missing_required_fields():
    items = [
        {"oid": "no_coords", "lastmjd": 60000.0},                       # no ra/dec
        {"oid": "no_lastmjd", "meanra": 180.0, "meandec": -30.0},       # no time
        {"meanra": 180.0, "meandec": -30.0, "lastmjd": 60000.0},         # no oid
        _row("good", 180.0, -30.0, 60000.0),
    ]
    out = filter_neighbors(items, lastmjd=60000.0)
    assert [r["oid"] for r in out] == ["good"]
