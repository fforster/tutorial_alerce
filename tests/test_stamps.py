"""Tests for shape_stamps_context: picker construction + URL building."""
from __future__ import annotations

from src.services.stamps import shape_stamps_context


def _ztf_det(mjd, fid, candid, has_stamp=True):
    return {"mjd": mjd, "fid": fid, "candid": candid, "has_stamp": has_stamp}


def _lsst_det(mjd, band_int, mid, has_stamp=True):
    return {
        "mjd": mjd, "band": band_int, "measurement_id": mid,
        "band_map": {"1": "g", "2": "r", "3": "i", "4": "z", "5": "y", "6": "u"},
        "has_stamp": has_stamp,
    }


def test_ztf_picker_sorted_mjd_desc_and_identifier_is_string():
    raw = {"detections": [
        _ztf_det(60001.0, 1, 111),
        _ztf_det(60005.0, 2, 222),
        _ztf_det(60003.0, 1, 333),
    ]}
    ctx = shape_stamps_context(raw, survey="ztf", oid="ZTF21abc", identifier=None)
    assert [d["identifier"] for d in ctx["detections"]] == ["222", "333", "111"]
    assert ctx["selected"]["identifier"] == "222"


def test_ztf_picker_drops_detections_without_stamp():
    raw = {"detections": [
        _ztf_det(60001.0, 1, 111, has_stamp=False),
        _ztf_det(60002.0, 2, 222, has_stamp=True),
    ]}
    ctx = shape_stamps_context(raw, survey="ztf", oid="x", identifier=None)
    assert [d["identifier"] for d in ctx["detections"]] == ["222"]


def test_selected_identifier_wins_when_provided():
    raw = {"detections": [
        _ztf_det(60005.0, 1, 111),
        _ztf_det(60001.0, 1, 222),
    ]}
    ctx = shape_stamps_context(raw, survey="ztf", oid="x", identifier="222")
    # 111 is the most recent but we asked for 222.
    assert ctx["selected"]["identifier"] == "222"


def test_selected_falls_back_to_most_recent_if_identifier_missing():
    raw = {"detections": [_ztf_det(60005.0, 1, 111), _ztf_det(60001.0, 1, 222)]}
    ctx = shape_stamps_context(raw, survey="ztf", oid="x", identifier="does-not-exist")
    assert ctx["selected"]["identifier"] == "111"


def test_ztf_stamp_urls_use_avro_host_and_type_names():
    raw = {"detections": [_ztf_det(60000.0, 1, 42)]}
    ctx = shape_stamps_context(raw, survey="ztf", oid="ZTF21abc", identifier=None)
    urls = ctx["stamp_urls"]
    assert set(urls) == {"science", "template", "difference"}
    assert "avro.alerce.online" in urls["science"]
    assert "oid=ZTF21abc" in urls["science"]
    assert "candid=42" in urls["science"]
    assert "type=science" in urls["science"]
    assert "type=template" in urls["template"]
    assert "type=difference" in urls["difference"]


def test_lsst_stamp_urls_use_cutout_names_and_measurement_id():
    raw = {"detections": [_lsst_det(60000.0, 2, 99999999999)]}
    ctx = shape_stamps_context(raw, survey="lsst", oid="LSST-1", identifier=None)
    urls = ctx["stamp_urls"]
    assert "api-lsst.alerce.online" in urls["science"]
    assert "measurement_id=99999999999" in urls["science"]
    assert "stamp_type=cutoutScience" in urls["science"]
    assert "stamp_type=cutoutTemplate" in urls["template"]
    assert "stamp_type=cutoutDifference" in urls["difference"]
    assert "file_format=fits" in urls["science"]


def test_lsst_band_letter_resolved_via_band_map():
    raw = {"detections": [_lsst_det(60000.0, 4, 1)]}  # band 4 → "z"
    ctx = shape_stamps_context(raw, survey="lsst", oid="x", identifier=None)
    assert ctx["detections"][0]["band"] == "z"


def test_empty_detections_yields_empty_picker_and_no_urls():
    ctx = shape_stamps_context({"detections": []}, survey="ztf", oid="x", identifier=None)
    assert ctx["detections"] == []
    assert ctx["selected"] is None
    assert ctx["stamp_urls"] == {}


def test_large_lsst_measurement_id_preserved_as_string():
    raw = {"detections": [_lsst_det(60000.0, 1, 9007199254740993)]}  # > 2**53
    ctx = shape_stamps_context(raw, survey="lsst", oid="x", identifier=None)
    assert ctx["selected"]["identifier"] == "9007199254740993"


def test_stamp_url_templates_use_ident_placeholder():
    raw = {"detections": [_ztf_det(60000.0, 1, 42)]}
    ctx = shape_stamps_context(raw, survey="ztf", oid="ZTF21abc", identifier=None)
    tmpls = ctx["stamp_url_templates"]
    assert set(tmpls) == {"science", "template", "difference"}
    for t, url in tmpls.items():
        assert "__IDENT__" in url
        assert "ZTF21abc" in url


def test_stamp_url_templates_present_even_when_no_selection():
    ctx = shape_stamps_context({"detections": []}, survey="lsst", oid="LSST-1", identifier=None)
    # URL-based stamp fetches make no sense without a selection, but templates
    # describe the URL shape and should always be emitted so the client helper
    # works uniformly.
    tmpls = ctx["stamp_url_templates"]
    assert set(tmpls) == {"science", "template", "difference"}
    assert "__IDENT__" in tmpls["science"]


def test_picker_includes_utc_string_per_detection():
    """The dropdown options need a UTC date next to the MJD; the service
    pre-formats it so the template stays a one-liner. MJD 60000 sits in
    Feb 2023 — pin the day to lock the conversion to MJD-40587 + UTC."""
    raw = {"detections": [_ztf_det(60000.5, 1, 42)]}
    ctx = shape_stamps_context(raw, survey="ztf", oid="ZTF21abc", identifier=None)
    row = ctx["detections"][0]
    assert row["mjd_utc"].startswith("2023-02-25")
    assert row["mjd_utc"].endswith("UTC")


def test_picker_utc_is_blank_for_missing_mjd():
    """Defensive: a row that somehow lacks mjd shouldn't break — the
    template renders without the parenthetical UTC suffix."""
    from src.services.stamps import _mjd_to_utc
    assert _mjd_to_utc(None) == ""
    assert _mjd_to_utc(float("nan")) == ""
    assert _mjd_to_utc("not-a-number") == ""


def test_mjd_to_utc_subtracts_tai_offset_for_lsst():
    """LSST MJDs are `midpointMjdTai` (atomic time, currently UTC + 37 s).
    A naive (mjd - 40587) * 86400 conversion would label TAI as UTC and
    miss the calendar second by 37 s. The `scale="tai"` path subtracts the
    offset; `scale="utc"` (default, used for ZTF) leaves the value alone."""
    from src.services.stamps import _mjd_to_utc
    # MJD 60000.0 corresponds to 2023-02-25 00:00:00 in whatever scale it's
    # in. As UTC it stays 00:00:00; as TAI it lands 37 s earlier in UTC,
    # i.e. 2023-02-24 23:59:23 UTC.
    assert _mjd_to_utc(60000.0, "utc") == "2023-02-25 00:00:00 UTC"
    assert _mjd_to_utc(60000.0, "tai") == "2023-02-24 23:59:23 UTC"


def test_picker_uses_tai_offset_for_lsst_via_survey_config():
    """End-to-end: shape_stamps_context should consult SURVEY_CONFIG and
    apply the TAI offset for LSST without the caller having to know."""
    raw = {
        "detections": [
            {"measurement_id": "1", "mjd": 60000.0, "has_stamp": True, "band": "g",
             "band_map": {"g": "g"}},
        ]
    }
    ctx = shape_stamps_context(raw, survey="lsst", oid="L1", identifier=None)
    row = ctx["detections"][0]
    assert row["mjd_utc"] == "2023-02-24 23:59:23 UTC"


def test_stamp_url_templates_by_survey_carry_oid_and_ident_placeholders():
    """Per-survey templates feed cross-survey clicks (a ZTF point on an
    LSST view, or vice versa). Both __OID__ and __IDENT__ are placeholders
    here because the matched cross-survey OID isn't known at server-render
    time — the client substitutes both at click time using the LC chart's
    `$lcXOid` for the matched survey."""
    ctx = shape_stamps_context(
        {"detections": []}, survey="lsst", oid="LSST-1", identifier=None
    )
    by_survey = ctx["stamp_url_templates_by_survey"]
    assert set(by_survey) == {"lsst", "ztf"}
    for survey_key, tmpls in by_survey.items():
        assert set(tmpls) == {"science", "template", "difference"}
        for url in tmpls.values():
            assert "__OID__" in url
            assert "__IDENT__" in url
    # Sanity: each survey's URL points at the right host.
    assert "api-lsst.alerce.online" in by_survey["lsst"]["science"]
    assert "avro.alerce.online" in by_survey["ztf"]["science"]
