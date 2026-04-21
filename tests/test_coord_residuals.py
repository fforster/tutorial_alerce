"""Tests for shape_coord_residuals: mean subtraction, cos(dec) scaling, edges."""
from __future__ import annotations

import math

from src.services.coord_residuals import shape_coord_residuals


def _ztf(ra, dec, mjd, fid=1, candid="c0", has_stamp=True):
    return {"ra": ra, "dec": dec, "mjd": mjd, "fid": fid,
            "candid": candid, "has_stamp": has_stamp}


def _lsst(ra, dec, mjd, band=1, measurement_id=1, has_stamp=True):
    return {"ra": ra, "dec": dec, "mjd": mjd, "band": band,
            "band_map": {"1": "g", "2": "r"},
            "measurement_id": measurement_id, "has_stamp": has_stamp}


def test_residuals_are_mean_subtracted_in_arcsec():
    raw = {"detections": [
        _ztf(150.0, 30.0, 60000.0),
        _ztf(150.0 + 1/3600.0, 30.0, 60001.0),  # +1 arcsec in ra
        _ztf(150.0, 30.0 + 1/3600.0, 60002.0),  # +1 arcsec in dec
    ]}
    out = shape_coord_residuals(raw, survey="ztf")
    # Mean ra = 150 + 1/(3*3600); Δra at first point ≈ -1/3 arcsec * cos(30°).
    assert out["n_points"] == 3
    # Mean dec is 30 + tiny offset so cos(mean_dec) ≈ cos(30°) to ~1e-6.
    cos30 = math.cos(math.radians(30.0))
    d_ras = [p["d_ra"] for p in out["points"]]
    d_decs = [p["d_dec"] for p in out["points"]]
    assert math.isclose(d_ras[0], -1.0/3.0 * cos30, abs_tol=1e-5)
    assert math.isclose(d_ras[1], 2.0/3.0 * cos30, abs_tol=1e-5)
    assert math.isclose(d_ras[2], -1.0/3.0 * cos30, abs_tol=1e-5)
    assert math.isclose(sum(d_ras), 0.0, abs_tol=1e-9)
    assert math.isclose(sum(d_decs), 0.0, abs_tol=1e-9)


def test_cos_dec_factor_applied_on_delta_ra():
    # At dec=60°, 1" of RA-angle translates to 0.5" on-sky.
    raw = {"detections": [
        _ztf(150.0, 60.0, 60000.0),
        _ztf(150.0 + 1/3600.0, 60.0, 60001.0),  # +1" in RA angle
    ]}
    out = shape_coord_residuals(raw, survey="ztf")
    # Largest |Δra| should equal 0.5 arcsec * cos(60°)=0.25 — wait: mean offset
    # is +0.5", residual is ±0.5"; on-sky that's ±0.5 * cos(60°) = ±0.25".
    d_ras = sorted(abs(p["d_ra"]) for p in out["points"])
    assert math.isclose(d_ras[-1], 0.5 * math.cos(math.radians(60.0)), abs_tol=1e-9)


def test_mjd_bounds_returned():
    raw = {"detections": [
        _ztf(150.0, 30.0, 60005.0),
        _ztf(150.0, 30.0, 60001.0),
        _ztf(150.0, 30.0, 60003.0),
    ]}
    out = shape_coord_residuals(raw, survey="ztf")
    assert out["mjd_min"] == 60001.0
    assert out["mjd_max"] == 60005.0


def test_band_letter_attached_per_point():
    raw = {"detections": [
        _lsst(150.0, 30.0, 60000.0, band=1),
        _lsst(150.0, 30.0, 60001.0, band=2),
    ]}
    out = shape_coord_residuals(raw, survey="lsst")
    bands = [p["band"] for p in out["points"]]
    assert bands == ["g", "r"]


def test_identifier_and_has_stamp_propagated_for_click_sync():
    raw = {"detections": [
        _ztf(150.0, 30.0, 60000.0, candid="111", has_stamp=True),
        _ztf(150.0, 30.0, 60001.0, candid=2222, has_stamp=False),
    ]}
    out = shape_coord_residuals(raw, survey="ztf")
    # Candid coerced to string so 64-bit LSST ids survive JSON round-trips.
    assert [p["identifier"] for p in out["points"]] == ["111", "2222"]
    assert [p["has_stamp"] for p in out["points"]] == [True, False]


def test_lsst_identifier_uses_measurement_id():
    raw = {"detections": [
        _lsst(150.0, 30.0, 60000.0, measurement_id=9123456789012345),
        _lsst(150.0, 30.0, 60001.0, measurement_id=9123456789012346),
    ]}
    out = shape_coord_residuals(raw, survey="lsst")
    assert out["points"][0]["identifier"] == "9123456789012345"


def test_rows_missing_ra_dec_or_mjd_are_dropped():
    raw = {"detections": [
        _ztf(150.0, 30.0, 60000.0),
        {"ra": None, "dec": 30.0, "mjd": 60001.0, "fid": 1},
        {"ra": 150.0, "mjd": 60002.0, "fid": 1},  # no dec
        {"ra": 150.0, "dec": 30.0, "fid": 1},      # no mjd
        _ztf(150.0 + 1/3600.0, 30.0, 60003.0),
    ]}
    out = shape_coord_residuals(raw, survey="ztf")
    assert out["n_points"] == 2


def test_single_or_empty_detection_returns_no_points():
    assert shape_coord_residuals({"detections": []}, survey="ztf")["points"] == []
    one = {"detections": [_ztf(150.0, 30.0, 60000.0)]}
    out = shape_coord_residuals(one, survey="ztf")
    assert out["points"] == []
    assert out["mjd_min"] is None
    assert out["mjd_max"] is None
