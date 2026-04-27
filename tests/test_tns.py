"""Tests for the TNS htmx-bridge parser.

We don't hit the network — `parse_tns_fragment` takes the raw HTML string,
which is the only thing that can realistically drift upstream. The fetcher
(`get_tns_info`) is a thin httpx wrapper around the same parser, so the
interesting logic is all in the regex extraction.
"""
from __future__ import annotations

from src.services.tns import parse_tns_fragment


# Canonical fragment shape: 3-cell tbody row with ids "type"/"name"/"redshift"
# plus a <a id="tns-link"> down below. Stripped of the ALeRCE stylesheet link
# since we never render it.
SAMPLE_HIT = """
<div class="tw-w-full">
  <table>
    <tbody>
      <tr>
        <td id="type" class="tw-text-center">SN Ia</td>
        <td id="name" class="tw-text-center">2025twl</td>
        <td id="redshift" class="tw-text-center">0.043</td>
      </tr>
    </tbody>
  </table>
  <a id="tns-link" href="https://www.wis-tns.org/object/2025twl">TNS</a>
</div>
"""

# Empty-result shape: the endpoint returns 200 with an empty <tbody>, so we
# must detect "no name → no match" and return None.
SAMPLE_MISS = """
<div class="tw-w-full">
  <table><tbody></tbody></table>
</div>
"""

# Seen on unclassified objects: name is present, type (class) and redshift
# cells render empty. We should still return a dict — the TNS name + link is
# useful on its own.
SAMPLE_UNCLASSIFIED = """
<table>
  <tr>
    <td id="type"></td>
    <td id="name">2025xyz</td>
    <td id="redshift"></td>
  </tr>
</table>
<a id="tns-link" href="https://www.wis-tns.org/object/2025xyz">TNS</a>
"""


def test_parse_hit():
    out = parse_tns_fragment(SAMPLE_HIT)
    assert out == {
        "type": "SN Ia",
        "name": "2025twl",
        "redshift": 0.043,
        "url": "https://www.wis-tns.org/object/2025twl",
    }


def test_parse_miss_returns_none():
    assert parse_tns_fragment(SAMPLE_MISS) is None


def test_parse_unclassified_keeps_name_drops_class_and_z():
    out = parse_tns_fragment(SAMPLE_UNCLASSIFIED)
    assert out is not None
    assert out["name"] == "2025xyz"
    assert out["type"] is None
    assert out["redshift"] is None
    assert out["url"].endswith("/2025xyz")


def test_parse_missing_link_falls_back_to_tns_url():
    """If the fragment is missing the <a id="tns-link">, we still want a
    clickable URL — synthesize the canonical /object/<name> form so the UI
    stays useful."""
    frag = """
    <td id="type">SN II</td>
    <td id="name">2024abc</td>
    <td id="redshift">0.12</td>
    """
    out = parse_tns_fragment(frag)
    assert out is not None
    assert out["url"] == "https://www.wis-tns.org/object/2024abc"


def test_parse_non_numeric_redshift_becomes_none():
    """Upstream sometimes renders '—' or 'null' for missing z. Treat anything
    that isn't float-parseable as None rather than crashing the panel."""
    frag = """
    <td id="type">SN Ia</td>
    <td id="name">2025qqq</td>
    <td id="redshift">—</td>
    <a id="tns-link" href="https://www.wis-tns.org/object/2025qqq">TNS</a>
    """
    out = parse_tns_fragment(frag)
    assert out is not None
    assert out["redshift"] is None
