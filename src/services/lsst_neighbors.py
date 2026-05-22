"""LSST neighbour cone-search for the Aladin sky-view overlay.

Returns LSST objects whose `lastmjd` falls within `LSST_NEIGHBORS_LASTMJD_WINDOW`
days of a reference time AND whose mean position lies within
`LSST_NEIGHBORS_RADIUS_ARCSEC` of a reference RA/Dec. The intent is to surface
contemporaneous detections — possible asteroid / satellite trails — that the
detail view might otherwise miss.

We always query the LSST endpoint, irrespective of the detail view's survey:
LSST objects can lie near ZTF positions too, and the question "what *LSST*
sources were active here" is what trail-hunting cares about.

Upstream ordering matters: the default `probability DESC` ranking does a
full scan and blows past the 30s httpx ceiling on dense fields. Switching
to `lastmjd DESC` both makes the call fast (<2s consistently) AND makes
the upstream's `lastmjd: [lo, hi]` filter actually take effect — under
probability ordering it was silently ignored. So we now pass both.
We still re-check the window in Python as a belt-and-braces guard.
"""
from __future__ import annotations

from typing import Any

from . import alerce_client

LSST_NEIGHBORS_RADIUS_ARCSEC = 600.0          # 10 arcmin
LSST_NEIGHBORS_LASTMJD_WINDOW = 2.0 / 24.0    # ±2 hours, in days
# Upstream `list_objects` reliably times out above ~100 — 200 hits the 30s
# httpx ceiling, 100 returns in ~2s. The ±2 hr × 10 arcmin window is narrow
# enough that 100 is plenty in practice (most fields produce single-digit
# match counts).
_PAGE_SIZE = 100


def _maybe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def filter_neighbors(
    items: list[dict[str, Any]],
    *,
    lastmjd: float,
    exclude_oid: str | None = None,
) -> list[dict[str, Any]]:
    """Pure-Python filter for the cone-search result.

    Extracted so tests can exercise it without monkeypatching the HTTP client.
    """
    lo = lastmjd - LSST_NEIGHBORS_LASTMJD_WINDOW
    hi = lastmjd + LSST_NEIGHBORS_LASTMJD_WINDOW
    out: list[dict[str, Any]] = []
    # Upstream often returns the same oid twice (per-classifier listing).
    # Dedupe so the legend count and Aladin overlay don't double-mark the
    # same source.
    seen: set[str] = set()
    for r in items:
        oid_raw = r.get("oid")
        if oid_raw is None:
            continue
        oid = str(oid_raw)
        if exclude_oid and oid == exclude_oid:
            continue
        if oid in seen:
            continue
        ra = _maybe_float(r.get("meanra"))
        dec = _maybe_float(r.get("meandec"))
        mjd = _maybe_float(r.get("lastmjd"))
        if ra is None or dec is None or mjd is None:
            continue
        if not (lo <= mjd <= hi):
            continue
        seen.add(oid)
        out.append({"oid": oid, "ra": ra, "dec": dec, "lastmjd": mjd})
    return out


async def get_lsst_neighbors(
    *,
    ra: float,
    dec: float,
    lastmjd: float,
    exclude_oid: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "ra": ra,
        "dec": dec,
        "radius": LSST_NEIGHBORS_RADIUS_ARCSEC,
        "lastmjd": [
            lastmjd - LSST_NEIGHBORS_LASTMJD_WINDOW,
            lastmjd + LSST_NEIGHBORS_LASTMJD_WINDOW,
        ],
        "page": 1,
        "page_size": _PAGE_SIZE,
        "count": False,
        # Override the default probability-DESC ordering. On dense fields
        # (e.g. ra=239.76 dec=-12.42) the upstream's probability ranking
        # blows past the 30s httpx ceiling; lastmjd-DESC returns in <2s.
        # Under this ordering the upstream's lastmjd-range filter also
        # takes effect (it's silently ignored under probability ordering),
        # so passing it here actually prunes server-side too.
        "order_by": "lastmjd",
        "order_mode": "DESC",
    }
    raw = await alerce_client.list_objects("lsst", params)
    if isinstance(raw, dict):
        items = raw.get("items") or []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    return filter_neighbors(items, lastmjd=lastmjd, exclude_oid=exclude_oid)
