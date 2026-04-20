"""Tests for shape_lightcurve: bucketing, band ordering, unit handling."""
from __future__ import annotations

import math

from src.services.lightcurve import shape_lightcurve


def _ztf_det(mjd, fid, magpsf, sigmapsf=0.05, candid="100"):
    return {
        "mjd": mjd, "fid": fid, "magpsf": magpsf,
        "sigmapsf": sigmapsf, "candid": candid, "isdiffpos": 1,
    }


def _lsst_det(mjd, band_int, flux, flux_err=10.0, measurement_id=1):
    return {
        "mjd": mjd, "band": band_int,
        "band_map": {"1": "g", "2": "r", "3": "i", "4": "z", "5": "y", "6": "u"},
        "psfFlux": flux, "psfFluxErr": flux_err,
        "measurement_id": measurement_id,
    }


def test_ztf_bucket_by_band_and_convert_mag_to_njy():
    raw = {"detections": [
        _ztf_det(60000.0, 1, 20.0, candid="1"),
        _ztf_det(60001.0, 2, 19.0, candid="2"),
        _ztf_det(60002.0, 1, 19.5, candid="3"),
    ]}
    out = shape_lightcurve(raw, survey="ztf")
    band_names = [b["name"] for b in out["bands"]]
    # ZTF bands appear in survey canonical order g, r, i
    assert band_names == ["g", "r"]
    assert out["n_det"] == 3
    # mag 20 → 10^((31.4-20)/2.5) ≈ 36307.8 nJy
    g_first = out["bands"][0]["points"][0]
    assert math.isclose(g_first["flux"], 10 ** ((31.4 - 20.0) / 2.5), rel_tol=1e-9)


def test_ztf_points_sorted_by_mjd():
    raw = {"detections": [
        _ztf_det(60005.0, 1, 20.0, candid="b"),
        _ztf_det(60001.0, 1, 20.0, candid="a"),
    ]}
    out = shape_lightcurve(raw, survey="ztf")
    assert [p["mjd"] for p in out["bands"][0]["points"]] == [60001.0, 60005.0]


def test_ztf_drops_rows_missing_mag_or_mjd():
    raw = {"detections": [
        _ztf_det(60000.0, 1, 20.0, candid="1"),
        {"mjd": 60001.0, "fid": 2, "candid": "2"},         # no magpsf
        {"fid": 1, "magpsf": 20.0, "candid": "3"},          # no mjd
    ]}
    out = shape_lightcurve(raw, survey="ztf")
    assert out["n_det"] == 1


def test_lsst_passes_flux_through_and_resolves_band_letter():
    raw = {"detections": [
        _lsst_det(60000.0, 1, 1234.5),
        _lsst_det(60001.0, 4, 500.0),
    ]}
    out = shape_lightcurve(raw, survey="lsst")
    # LSST canonical order is u,g,r,i,z,y so g comes before z
    band_names = [b["name"] for b in out["bands"]]
    assert band_names == ["g", "z"]
    assert out["bands"][0]["points"][0]["flux"] == 1234.5
    assert out["bands"][1]["points"][0]["flux"] == 500.0


def test_empty_detections_returns_zero_count():
    out = shape_lightcurve({"detections": []}, survey="lsst")
    assert out["n_det"] == 0
    assert out["bands"] == []
    assert out["n_fp"] == 0
    assert out["forced_phot_bands"] == []


def test_identifier_preserved_as_string():
    raw = {"detections": [_ztf_det(60000.0, 1, 20.0, candid=12345)]}
    out = shape_lightcurve(raw, survey="ztf")
    p = out["bands"][0]["points"][0]
    assert p["identifier"] == "12345"


def test_has_stamp_flag_propagates_from_upstream():
    raw = {"detections": [
        {**_ztf_det(60000.0, 1, 20.0, candid="1"), "has_stamp": True},
        {**_ztf_det(60001.0, 1, 20.0, candid="2"), "has_stamp": False},
        _ztf_det(60002.0, 1, 20.0, candid="3"),  # has_stamp missing → False
    ]}
    out = shape_lightcurve(raw, survey="ztf")
    flags = [p["has_stamp"] for p in out["bands"][0]["points"]]
    assert flags == [True, False, False]


def test_lsst_identifier_uses_measurement_id():
    raw = {"detections": [_lsst_det(60000.0, 1, 1000.0, measurement_id=9123456789012345)]}
    out = shape_lightcurve(raw, survey="lsst")
    assert out["bands"][0]["points"][0]["identifier"] == "9123456789012345"


def test_lsst_fp_buckets_into_forced_phot_bands():
    raw = {"detections": [_lsst_det(60000.0, 1, 1000.0)]}
    fp = [
        _lsst_det(59999.0, 1, 50.0, measurement_id=10),
        _lsst_det(59998.0, 2, 30.0, measurement_id=11),
    ]
    out = shape_lightcurve(raw, survey="lsst", fp_raw=fp)
    assert out["n_fp"] == 2
    fp_names = [b["name"] for b in out["forced_phot_bands"]]
    assert fp_names == ["g", "r"]
    # Detections are independent of FP.
    assert out["n_det"] == 1
    assert [b["name"] for b in out["bands"]] == ["g"]


def test_ztf_fp_converts_mag_to_njy_same_as_detections():
    raw = {"detections": []}
    fp = [_ztf_det(60000.0, 1, 20.0, candid=999)]
    out = shape_lightcurve(raw, survey="ztf", fp_raw=fp)
    import math as _m
    assert out["n_fp"] == 1
    assert _m.isclose(
        out["forced_phot_bands"][0]["points"][0]["flux"],
        10 ** ((31.4 - 20.0) / 2.5),
        rel_tol=1e-9,
    )


def test_fp_none_is_same_as_no_fp():
    raw = {"detections": [_lsst_det(60000.0, 1, 1000.0)]}
    a = shape_lightcurve(raw, survey="lsst", fp_raw=None)
    b = shape_lightcurve(raw, survey="lsst", fp_raw=[])
    assert a == b
    assert a["n_fp"] == 0
