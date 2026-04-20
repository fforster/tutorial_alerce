"""External archive URL builder tests."""
from __future__ import annotations

from src.services.other_archives import build_archive_links


def test_ztf_alerce_uses_short_url():
    links = build_archive_links(survey="ztf", oid="ZTF21abc", ra=None, dec=None)
    names = {link["name"]: link["url"] for link in links}
    assert "ALeRCE Explorer" in names
    assert names["ALeRCE Explorer"] == "https://alerce.online/object/ZTF21abc"


def test_lsst_alerce_uses_query_params():
    links = build_archive_links(survey="lsst", oid="123456789012345678", ra=None, dec=None)
    names = {link["name"]: link["url"] for link in links}
    assert "survey=lsst" in names["ALeRCE Explorer"]
    assert "oid=123456789012345678" in names["ALeRCE Explorer"]


def test_without_coords_only_alerce_link():
    links = build_archive_links(survey="ztf", oid="ZTF21abc", ra=None, dec=None)
    assert len(links) == 1
    assert links[0]["name"] == "ALeRCE Explorer"


def test_with_coords_emits_full_set():
    links = build_archive_links(survey="ztf", oid="ZTF21abc", ra=180.0, dec=-30.0)
    names = [link["name"] for link in links]
    # Spot-check a handful of expected archives
    for expected in ["DESI Legacy Survey DR11", "SIMBAD", "TNS", "VizieR", "ALeRCE Finding Chart"]:
        assert expected in names


def test_finding_chart_uses_oid():
    links = build_archive_links(survey="ztf", oid="ZTF21abc", ra=180.0, dec=-30.0)
    fc = next(link for link in links if link["name"] == "ALeRCE Finding Chart")
    assert "oid=ZTF21abc" in fc["url"]
