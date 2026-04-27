"""Tests for shape_probability_context: grouping, default selection."""
from __future__ import annotations

from src.services.probability import shape_probability_context


def _row(classifier, version, class_name, prob):
    return {
        "classifier_name": classifier,
        "classifier_version": version,
        "class_name": class_name,
        "probability": prob,
    }


def test_groups_by_classifier_name_and_version():
    raw = [
        _row("lc_classifier_top", "1.0", "SN", 0.8),
        _row("lc_classifier_top", "1.0", "AGN", 0.2),
        _row("lc_classifier_transient", "2.0", "SN", 0.5),
        _row("lc_classifier_transient", "2.0", "AGN", 0.5),
    ]
    out = shape_probability_context(raw, survey="lsst")
    keys = [g["key"] for g in out["groups"]]
    assert keys == ["lc_classifier_top v1.0", "lc_classifier_transient v2.0"]


def test_default_key_matches_survey_primary_classifier():
    raw = [
        _row("lc_classifier_transient", "2.0", "SN", 0.5),
        _row("stamp_classifier_rubin_beta_20260421", "2.0.2", "SN", 0.8),
    ]
    out = shape_probability_context(raw, survey="lsst")
    # SC("lsst").default_classifier is the primary; the radar panel pins
    # this group as the initial selection.
    assert out["default_key"] == "stamp_classifier_rubin_beta_20260421 v2.0.2"


def test_default_key_falls_back_to_first_when_primary_absent():
    raw = [_row("lc_classifier_transient", "2.0", "SN", 0.5)]
    out = shape_probability_context(raw, survey="lsst")
    assert out["default_key"] == "lc_classifier_transient v2.0"


def test_empty_raw_returns_no_groups():
    out = shape_probability_context([], survey="ztf")
    assert out["groups"] == []
    assert out["default_key"] is None


def test_classes_sorted_by_probability_desc_and_max_flag_set():
    raw = [
        _row("lc_classifier", "1", "AGN", 0.3),
        _row("lc_classifier", "1", "SN", 0.6),
        _row("lc_classifier", "1", "QSO", 0.1),
    ]
    out = shape_probability_context(raw, survey="ztf")
    classes = out["groups"][0]["classes"]
    assert [c["class_name"] for c in classes] == ["SN", "AGN", "QSO"]
    assert [c["is_max"] for c in classes] == [True, False, False]


def test_classifier_override_wins_default_key_over_survey_primary():
    """Deep-link URLs carry the classifier the user was searching under;
    shape must prefer that group even when the survey's primary classifier
    is also present."""
    raw = [
        _row("lc_classifier_top", "1.0", "SN", 0.8),
        _row("lc_classifier_BHRF_forced_phot", "2.0", "SN", 0.7),
    ]
    out = shape_probability_context(
        raw, survey="lsst", classifier="lc_classifier_BHRF_forced_phot"
    )
    assert out["default_key"] == "lc_classifier_BHRF_forced_phot v2.0"


def test_classifier_override_falls_back_when_no_match():
    """Unknown classifier override → survey primary wins."""
    raw = [
        _row("lc_classifier_top", "1.0", "SN", 0.8),
        _row("lc_classifier_transient", "2.0", "SN", 0.5),
    ]
    out = shape_probability_context(raw, survey="lsst", classifier="not_a_classifier")
    assert out["default_key"] == "lc_classifier_top v1.0"


def test_rows_missing_class_name_are_dropped():
    raw = [
        _row("lc_classifier", "1", "SN", 0.9),
        {"classifier_name": "lc_classifier", "classifier_version": "1",
         "probability": 0.1},  # no class_name
    ]
    out = shape_probability_context(raw, survey="ztf")
    assert len(out["groups"][0]["classes"]) == 1
