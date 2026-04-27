from src.services.classifiers import tidy_classifiers


def test_tidy_dedupes_by_name_and_merges_classes():
    raw = [
        {"classifier_name": "lc_classifier", "classifier_version": "v1",
         "classes": ["SN", "AGN"]},
        {"classifier_name": "lc_classifier", "classifier_version": "v2",
         "classes": ["AGN", "VS"]},
    ]
    out = tidy_classifiers(raw, "ztf")
    assert len(out) == 1
    assert out[0]["classifier_name"] == "lc_classifier"
    assert out[0]["classes"] == ["SN", "AGN", "VS"]
    # Versions are collected in input order; latest is the lex-max so the
    # "Latest" dropdown option resolves to the same string regardless of
    # ordering quirks upstream.
    assert out[0]["versions"] == ["v1", "v2"]
    assert out[0]["latest_version"] == "v2"


def test_tidy_latest_version_is_lex_max():
    """Lex-max picks the highest version in N.N.N space — works for the
    versions actually returned by ALeRCE in practice (e.g. 1.0.0 < 1.0.4)."""
    raw = [
        {"classifier_name": "stamp_classifier", "classifier_version": "1.0.4",
         "classes": ["bogus"]},
        {"classifier_name": "stamp_classifier", "classifier_version": "1.0.0",
         "classes": ["bogus"]},
    ]
    out = tidy_classifiers(raw, "ztf")
    assert out[0]["latest_version"] == "1.0.4"
    assert set(out[0]["versions"]) == {"1.0.0", "1.0.4"}


def test_tidy_no_version_field_yields_none_latest():
    raw = [{"classifier_name": "lc_classifier_top", "classes": []}]
    out = tidy_classifiers(raw, "lsst")
    assert out[0]["versions"] == []
    assert out[0]["latest_version"] is None


def test_tidy_sorts_by_priority():
    raw = [
        {"classifier_name": "stamp_classifier", "classes": []},
        {"classifier_name": "lc_classifier", "classes": []},
    ]
    out = tidy_classifiers(raw, "ztf")
    assert [e["classifier_name"] for e in out] == ["lc_classifier", "stamp_classifier"]


def test_tidy_accepts_dict_wrapper():
    raw = {"classifiers": [{"classifier_name": "lc_classifier_top", "classes": ["SN"]}]}
    out = tidy_classifiers(raw, "lsst")
    assert out[0]["classifier_name"] == "lc_classifier_top"


def test_tidy_formats_display_name():
    raw = [{"classifier_name": "lc_classifier_top", "classes": []}]
    out = tidy_classifiers(raw, "lsst")
    assert out[0]["formatted_name"] == "lc classifier top"
