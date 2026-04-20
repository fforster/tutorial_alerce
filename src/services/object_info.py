"""Object-detail shaping: call the ALeRCE object endpoint and normalize to a
common schema the basic-information template renders.

Field differences handled here (not in the template):
  - ZTF:  ndet            (no n_det)         → n_det
          ncovhist-ndethist                  → n_non_det (approx)
          corrected, stellar                 → kept
  - LSST: n_det, n_non_det, n_forced         → kept
          no corrected/stellar
"""
from __future__ import annotations

from typing import Any

from . import alerce_client
from .coordinates import dec_to_dms, ra_to_hms
from .other_archives import build_archive_links


def _maybe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _maybe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def shape_object_info(raw: dict[str, Any], *, survey: str) -> dict[str, Any]:
    oid = str(raw.get("oid")) if raw.get("oid") is not None else None
    ra = _maybe_float(raw.get("meanra"))
    dec = _maybe_float(raw.get("meandec"))
    firstmjd = _maybe_float(raw.get("firstmjd"))
    lastmjd = _maybe_float(raw.get("lastmjd"))
    delta = _maybe_float(raw.get("deltamjd") or raw.get("deltajd"))
    if delta is None and firstmjd is not None and lastmjd is not None:
        delta = lastmjd - firstmjd

    if survey == "ztf":
        n_det = _maybe_int(raw.get("ndet"))
        ndethist = _maybe_int(raw.get("ndethist"))
        ncovhist = _maybe_int(raw.get("ncovhist"))
        n_non_det = (
            ncovhist - ndethist
            if ncovhist is not None and ndethist is not None
            else None
        )
        corrected = raw.get("corrected")
        stellar = raw.get("stellar")
    else:
        n_det = _maybe_int(raw.get("n_det"))
        n_non_det = _maybe_int(raw.get("n_non_det"))
        corrected = None
        stellar = None
    n_forced = _maybe_int(raw.get("n_forced"))

    ra_hms = ra_to_hms(ra) if ra is not None else None
    dec_dms = dec_to_dms(dec) if dec is not None else None

    archives = build_archive_links(survey=survey, oid=oid or "", ra=ra, dec=dec)

    return {
        "oid": oid,
        "survey": survey,
        "ra": ra,
        "dec": dec,
        "ra_hms": ra_hms,
        "dec_dms": dec_dms,
        "firstmjd": firstmjd,
        "lastmjd": lastmjd,
        "delta_mjd": delta,
        "n_det": n_det,
        "n_non_det": n_non_det,
        "n_forced": n_forced,
        "corrected": corrected,
        "stellar": stellar,
        "archives": archives,
    }


async def get_object_info(*, survey: str, oid: str) -> dict[str, Any]:
    raw = await alerce_client.get_object(survey, oid)
    if not isinstance(raw, dict):
        raise ValueError(f"Unexpected object response shape: {type(raw).__name__}")
    return shape_object_info(raw, survey=survey)
