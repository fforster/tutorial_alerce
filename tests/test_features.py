"""Tests for the features service and /htmx/features route."""
from __future__ import annotations

import asyncio

from src.services import alerce_client, features as features_service
from src.services.features import (
    extract_parametric_fits,
    pick_default_version,
    shape_features,
)


def _spm_row(band_fid, version, *, prefix="SPM", **overrides):
    """Helper: synthesize a parametric-fit feature row for tests."""
    base = {"fid": band_fid, "version": version}
    base.update(overrides)
    base.setdefault("name", f"{prefix}_A")
    base.setdefault("value", 1.0)
    return base


def test_shape_features_sorts_and_labels_ztf_fids():
    raw = [
        {"name": "Amplitude", "value": 0.5, "fid": 2, "version": "v1"},
        {"name": "Multiband_period", "value": 3.14, "fid": 12, "version": "v1"},
        {"name": "Mean", "value": 20.1, "fid": 1, "version": "v1"},
        {"name": "Skew", "value": None, "fid": None, "version": "v1"},
    ]
    out = shape_features(raw, survey="ztf")
    assert out["n"] == 4
    # Single version: sort collapses to (band, name): g, multi, r, —.
    bands = [r["band"] for r in out["rows"]]
    assert bands == ["g", "multi", "r", "—"]
    names = [r["name"] for r in out["rows"]]
    assert names == ["Mean", "Multiband_period", "Amplitude", "Skew"]
    assert out["versions"] == ["v1"]
    assert out["default_version"] == "v1"
    assert out["n_by_version"] == {"v1": 4}


def test_shape_features_formats_values():
    raw = [
        {"name": "A", "value": 0.123456789, "fid": 1, "version": "v1"},
        {"name": "B", "value": None, "fid": 1, "version": "v1"},
        {"name": "C", "value": float("nan"), "fid": 1, "version": "v1"},
        {"name": "D", "value": 42, "fid": 1, "version": "v1"},
        {"name": "E", "value": "str", "fid": 1, "version": "v1"},
    ]
    out = shape_features(raw, survey="ztf")
    by_name = {r["name"]: r["value_display"] for r in out["rows"]}
    # %g trims trailing zeros and uses 6 sig figs.
    assert by_name["A"] == "0.123457"
    assert by_name["B"] == "—"
    assert by_name["C"] == "—"
    assert by_name["D"] == "42"
    assert by_name["E"] == "str"


def test_shape_features_skips_malformed_rows():
    """A bad row shouldn't nuke the whole table."""
    raw = [
        {"name": "good", "value": 1.0, "fid": 1},
        "not a dict",
        {"value": 1.0, "fid": 1},          # missing name
        {"name": "", "value": 1.0, "fid": 1},  # empty name
        None,
    ]
    out = shape_features(raw, survey="ztf")
    assert out["n"] == 1
    assert out["rows"][0]["name"] == "good"


def test_shape_features_handles_non_list():
    empty = {
        "rows": [], "versions": [], "n_by_version": {},
        "bands": [], "default_version": None, "n": 0,
    }
    assert shape_features(None, survey="ztf") == empty
    assert shape_features({"detections": []}, survey="ztf") == empty


def test_shape_features_groups_by_version_with_latest_default():
    """Multiple versions land in one response; the service preserves
    first-seen order (API convention: newest appended last) and defaults
    the picker to the last-seen version."""
    raw = [
        {"name": "A", "value": 1.0, "fid": 1, "version": "v1"},
        {"name": "B", "value": 2.0, "fid": 1, "version": "v1"},
        {"name": "A", "value": 1.1, "fid": 1, "version": "v2"},
        {"name": "A", "value": 1.2, "fid": 1, "version": "v3"},
        {"name": "B", "value": 2.2, "fid": 1, "version": "v3"},
    ]
    out = shape_features(raw, survey="ztf")
    assert out["versions"] == ["v1", "v2", "v3"]
    assert out["default_version"] == "v3"
    assert out["n_by_version"] == {"v1": 2, "v2": 1, "v3": 2}
    # Rows sorted (version_seen_index, band, name): all v1 first, then v2, v3.
    versions_in_order = [r["version"] for r in out["rows"]]
    assert versions_in_order == ["v1", "v1", "v2", "v3", "v3"]


def test_shape_features_missing_version_falls_back_to_placeholder():
    raw = [{"name": "A", "value": 1.0, "fid": 1}]  # no version key
    out = shape_features(raw, survey="ztf")
    assert out["versions"] == ["—"]
    assert out["default_version"] == "—"
    assert out["rows"][0]["version"] == "—"


def test_pick_default_version_prefers_pattern_match():
    """Versions matching the strict `N.N.N` scheme beat non-matching ones,
    regardless of insertion order — so `27.5.6` wins over
    `lc_classifier_1.2.1-P` even when the legacy label comes last."""
    assert pick_default_version(["27.5.6", "lc_classifier_1.2.1-P"]) == "27.5.6"
    assert pick_default_version(["lc_classifier_1.2.1-P", "27.5.6"]) == "27.5.6"


def test_pick_default_version_requires_pure_integer_third_segment():
    """Third segment must be pure digits — `25.0.1a8` and `23.12.26a85`
    don't qualify and fall through, leaving `27.5.6` as the only match."""
    assert pick_default_version(["23.12.26a85", "25.0.1a8", "27.5.6"]) == "27.5.6"
    # With no strict-match version, all candidates fall through to last-seen.
    assert pick_default_version(["23.12.26a85", "25.0.1a8"]) == "25.0.1a8"


def test_pick_default_version_sorts_by_all_three_numbers_desc():
    """Among strict-matched versions: sort (first, second, third) DESC."""
    # Second-number tiebreak when firsts match.
    assert pick_default_version(["27.4.9", "27.5.0"]) == "27.5.0"
    # Third-number tiebreak when first and second match.
    assert pick_default_version(["27.5.0", "27.5.6", "27.5.3"]) == "27.5.6"
    # Higher first beats higher second/third: 28.0.0 > 27.99.99.
    assert pick_default_version(["27.99.99", "28.0.0"]) == "28.0.0"


def test_pick_default_version_falls_back_to_last_seen_when_no_pattern_match():
    """No strict-matched versions → keep the old "newest appended last"
    behaviour so we don't regress on pre-N.N.N classifier labels."""
    assert pick_default_version(["foo", "bar", "baz"]) == "baz"
    assert pick_default_version(["—"]) == "—"


def test_pick_default_version_handles_empty():
    assert pick_default_version([]) is None


def test_shape_features_default_version_uses_pattern_picker():
    """shape_features delegates default_version selection, so it must pick
    `27.5.6` over the older `lc_classifier_1.2.1-P` even when the latter
    appears later in the bundled response."""
    raw = [
        {"name": "Multiband_period", "value": 10.16, "fid": 12, "version": "27.5.6"},
        {"name": "Multiband_period", "value": 0.465, "fid": 12,
         "version": "lc_classifier_1.2.1-P"},
    ]
    out = shape_features(raw, survey="ztf")
    assert out["default_version"] == "27.5.6"


def test_get_features_returns_unavailable_for_lsst(monkeypatch):
    """LSST has no features_url_template — the service must short-circuit
    without calling the API and return available=False."""
    calls: list[str] = []

    async def fake_get(url: str):
        calls.append(url)
        return []

    monkeypatch.setattr(alerce_client, "_get", fake_get)
    out = asyncio.run(features_service.get_features(survey="lsst", oid="1"))
    assert out == {
        "available": False, "rows": [], "n": 0,
        "versions": [], "n_by_version": {}, "bands": [],
        "default_version": None,
    }
    assert calls == []


# ── extract_parametric_fits ──────────────────────────────────────────────────

# Full SPM feature rows for one band + version. Every required SPM param must
# be present for the band to survive; χ² is optional.
def _full_spm(band_fid, version):
    params = {
        "SPM_A": 0.5, "SPM_beta": 0.3, "SPM_t0": 5.0, "SPM_gamma": 2.0,
        "SPM_tau_rise": 1.0, "SPM_tau_fall": 10.0, "SPM_chi": 0.9,
    }
    return [{"name": k, "value": v, "fid": band_fid, "version": version}
            for k, v in params.items()]


def _full_fleet(band_fid, version):
    params = {
        "fleet_a": 0.1, "fleet_w": 0.02, "fleet_m0": 20.0, "fleet_t0": 3.0,
        "fleet_chi": 1.2,
    }
    return [{"name": k, "value": v, "fid": band_fid, "version": version}
            for k, v in params.items()]


def _full_tde(band_fid, version):
    params = {"TDE_mag0": 19.5, "TDE_decay": 1.0, "TDE_decay_chi": 0.8}
    return [{"name": k, "value": v, "fid": band_fid, "version": version}
            for k, v in params.items()]


def test_extract_parametric_fits_picks_latest_version_only():
    """Two versions of SPM for band g; only the one picked by
    pick_default_version should appear in the output — never both. Otherwise
    the client would blend an old and a new fit."""
    rows = [*_full_spm(1, "1.0.0"), *_full_spm(1, "27.5.6")]
    # Tweak the older version's amplitude so we can tell them apart.
    for r in rows:
        if r["version"] == "1.0.0" and r["name"] == "SPM_A":
            r["value"] = 99.9
    out = extract_parametric_fits(rows, survey="ztf")
    assert set(out.keys()) == {"spm"}
    assert set(out["spm"].keys()) == {"g"}
    assert out["spm"]["g"]["A"] == 0.5  # from 27.5.6, not 99.9


def test_extract_parametric_fits_all_three_overlays_multi_band():
    """A mature object has SPM + FLEET + TDE params for multiple bands; the
    extractor must surface all three overlays with the right bands each."""
    rows = [
        *_full_spm(1, "27.5.6"), *_full_spm(2, "27.5.6"),
        *_full_fleet(1, "27.5.6"), *_full_fleet(2, "27.5.6"),
        *_full_tde(2, "27.5.6"),
    ]
    out = extract_parametric_fits(rows, survey="ztf")
    assert set(out.keys()) == {"spm", "fleet", "tde"}
    assert set(out["spm"].keys()) == {"g", "r"}
    assert set(out["fleet"].keys()) == {"g", "r"}
    assert set(out["tde"].keys()) == {"r"}  # g had no TDE rows
    # Short keys are stripped of the feature-name prefix.
    assert set(out["spm"]["g"].keys()) >= {"A", "beta", "t0", "gamma", "tau_rise", "tau_fall"}
    assert set(out["fleet"]["g"].keys()) >= {"a", "w", "m0", "t0"}
    assert set(out["tde"]["r"].keys()) >= {"mag0", "decay"}


def test_extract_parametric_fits_drops_bands_missing_required_params():
    """A band with only some of the required params never renders a
    half-complete curve — it's dropped entirely, not partially emitted."""
    rows = _full_spm(1, "27.5.6")
    # Remove tau_fall for band g entirely → g should fall out.
    rows = [r for r in rows if r["name"] != "SPM_tau_fall"]
    out = extract_parametric_fits(rows, survey="ztf")
    assert "spm" not in out  # no band survived → overlay key dropped


def test_extract_parametric_fits_treats_nan_as_missing():
    """NaN / None values fail the finite-float check and count as absent."""
    import math
    rows = _full_spm(1, "27.5.6")
    for r in rows:
        if r["name"] == "SPM_gamma":
            r["value"] = float("nan")
    out = extract_parametric_fits(rows, survey="ztf")
    assert out == {}


def test_extract_parametric_fits_chi_is_optional():
    """χ² missing shouldn't drop the band — it's a display-only field."""
    rows = [r for r in _full_spm(1, "27.5.6") if r["name"] != "SPM_chi"]
    out = extract_parametric_fits(rows, survey="ztf")
    assert "spm" in out and "g" in out["spm"]
    assert "chi" not in out["spm"]["g"]


def test_extract_parametric_fits_skips_multi_and_unknown_bands():
    """Parametric fits are per-band; rows tagged fid=12 (multi) or missing
    fid can't land in a per-band overlay even if every param is present."""
    rows = _full_spm(12, "27.5.6")  # fid=12 → "multi"
    out = extract_parametric_fits(rows, survey="ztf")
    assert out == {}


def test_extract_parametric_fits_empty_inputs():
    assert extract_parametric_fits(None, survey="ztf") == {}
    assert extract_parametric_fits([], survey="ztf") == {}
    assert extract_parametric_fits({"not": "a list"}, survey="ztf") == {}


def test_extract_parametric_fits_honors_version_demote_when_latest_has_no_fit():
    """When pick_default_version selects a version that happens to carry no
    parametric-fit rows, we emit nothing rather than falling back to an older
    version — matching the Multiband_period rule (consistency with the
    features modal)."""
    # Latest version (27.5.6) has only an unrelated feature; older version
    # carries a full SPM fit. Must not leak the older fit.
    rows = [
        *_full_spm(1, "1.0.0"),
        {"name": "Amplitude", "value": 0.5, "fid": 1, "version": "27.5.6"},
    ]
    out = extract_parametric_fits(rows, survey="ztf")
    assert out == {}


def test_get_features_fetches_and_shapes_for_ztf(monkeypatch):
    captured: list[str] = []

    async def fake_get(url: str):
        captured.append(url)
        return [
            {"name": "Amplitude", "value": 0.5, "fid": 2},
            {"name": "Multiband_period", "value": 1.234, "fid": 12},
        ]

    monkeypatch.setattr(alerce_client, "_get", fake_get)
    out = asyncio.run(features_service.get_features(survey="ztf", oid="ZTF20x"))
    assert out["available"] is True
    assert out["n"] == 2
    # URL hit the ZTF features endpoint.
    assert any("features" in u and "ZTF20x" in u for u in captured)
