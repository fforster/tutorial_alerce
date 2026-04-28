"""Tests for the catsHTM crossmatch shaper.

We exercise `shape_crossmatch` directly with the payload shapes catsHTM
returns in production: nested `{unit, value}` cells, `{unit, values:[…]}`
arrays, plain scalars, and the empty-body edge cases. The async fetcher
(`get_crossmatch`) is a thin httpx wrapper — its behavior is covered by
the route tests where the fetch is monkeypatched.
"""
from __future__ import annotations

from src.services.crossmatch import _format_value, shape_crossmatch


def test_shape_empty_returns_empty_list():
    assert shape_crossmatch([]) == []


def test_shape_non_list_returns_empty_list():
    # The endpoint very occasionally returns a bare object on misuse; treat
    # anything non-list as "no catalogs" rather than crashing the panel.
    assert shape_crossmatch({"DECaLS": {}}) == []
    assert shape_crossmatch(None) == []


def test_shape_drops_empty_catalogs():
    raw = [
        {"DECaLS": {}},
        {"GAIA/DR2": {"RA": {"unit": "deg", "value": 180.0}}},
        {"Empty": None},
    ]
    out = shape_crossmatch(raw)
    assert [c["name"] for c in out] == ["GAIA/DR2"]


def test_shape_handles_value_unit_pairs():
    raw = [
        {"DECaLS": {
            "RA": {"unit": "deg", "value": 180.000180},
            "Dec": {"unit": "deg", "value": 0.499322},
            "distance": {"unit": "arcsec", "value": 2.5256685},
        }},
    ]
    out = shape_crossmatch(raw)
    assert len(out) == 1
    cat = out[0]
    assert cat["name"] == "DECaLS"
    by_key = {f["key"]: f for f in cat["fields"]}
    assert by_key["RA"]["value"] == "180.000180"
    assert by_key["RA"]["unit"] == "deg"
    assert by_key["distance"]["value"] == "2.525669"
    assert by_key["distance"]["unit"] == "arcsec"


def test_shape_handles_values_arrays():
    # Some catsHTM cells return a list under `values` instead of a scalar
    # `value` (e.g. multi-epoch photometry summaries).
    raw = [
        {"X": {"mags": {"unit": "mag", "values": [21.0, 21.5, 22.1]}}},
    ]
    out = shape_crossmatch(raw)
    assert out[0]["fields"][0]["value"] == "21.000000, 21.500000, 22.100000"
    assert out[0]["fields"][0]["unit"] == "mag"


def test_shape_drops_blank_units():
    # catsHTM uses " " (single space) as a "dimensionless" sentinel — drop
    # it so the column header doesn't render an empty `[ ]` suffix.
    raw = [{"X": {"flag": {"unit": " ", "value": 1.0}}}]
    out = shape_crossmatch(raw)
    assert out[0]["fields"][0]["unit"] is None


def test_shape_treats_null_value_as_dash():
    # Missing photometry rides through as `value: null` — render as em-dash
    # so empty cells read as "no value" instead of "0".
    raw = [{"X": {"Flux_u": {"unit": "nanomaggies", "value": None}}}]
    out = shape_crossmatch(raw)
    assert out[0]["fields"][0]["value"] == "—"


def test_shape_keeps_scalar_strings():
    # Some catalogs sneak in plain strings (no {unit, value} envelope); pass
    # them through unchanged.
    raw = [{"X": {"label": "QSO"}}]
    out = shape_crossmatch(raw)
    assert out[0]["fields"][0]["value"] == "QSO"
    assert out[0]["fields"][0]["unit"] is None


def test_format_value_six_decimals_for_floats():
    assert _format_value(1.234567891) == "1.234568"
    assert _format_value(0.0) == "0.000000"


def test_format_value_keeps_ints_intact():
    # Integer flags shouldn't get .000000 — keep them as-is so they stay
    # readable in the panel.
    assert _format_value(7) == "7"


def test_format_value_renders_bools_as_words():
    assert _format_value(True) == "true"
    assert _format_value(False) == "false"
