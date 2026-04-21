"""Detection coordinate residuals, for moving-object detection.

Stationary transients have detection positions within ~arcsec of each other
once PSF-centroid noise is accounted for. Moving objects (asteroids passing
near a host) drift during the nights they're observed, producing an obvious
linear track in RA/Dec residual space. This service prepares that scatter.

Residuals are reported in arcseconds, computed against the unweighted mean
position, with a cos(dec) correction on Δra so the scatter reads as an
on-sky offset (not a naive spherical-coordinate difference).
"""
from __future__ import annotations

import math
from typing import Any

from . import alerce_client
from .survey_config import SC


def _band_letter(d: dict[str, Any], survey: str) -> str | None:
    if survey == "ztf":
        return {1: "g", 2: "r", 3: "i"}.get(d.get("fid"))
    band_map = d.get("band_map") or {}
    b = d.get("band")
    return band_map.get(str(b)) if b is not None else None


def _identifier(d: dict[str, Any], survey: str) -> str | None:
    key = "candid" if survey == "ztf" else "measurement_id"
    v = d.get(key)
    return str(v) if v is not None else None


def _rows_from_detections(dets: list[dict[str, Any]], survey: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for d in dets:
        ra = d.get("ra")
        dec = d.get("dec")
        mjd = d.get("mjd")
        if ra is None or dec is None or mjd is None:
            continue
        rows.append({
            "ra": float(ra), "dec": float(dec), "mjd": float(mjd),
            "band": _band_letter(d, survey),
            # identifier + has_stamp let scatter clicks drive the stamp
            # panel via the shared selection helper (same contract the light
            # curve already uses).
            "identifier": _identifier(d, survey),
            "has_stamp": bool(d.get("has_stamp")),
        })
    return rows


def shape_coord_residuals(raw: dict[str, Any], *, survey: str) -> dict[str, Any]:
    """Compute Δra/Δdec residuals in arcsec against the mean detection position.

    Δra includes a cos(mean_dec) factor so the scatter plot shows a true
    on-sky offset. With fewer than 2 points there's no residual to plot.
    """
    rows = _rows_from_detections(raw.get("detections") or [], survey)
    if len(rows) < 2:
        return {"points": [], "n_points": len(rows),
                "mean_ra": None, "mean_dec": None,
                "mjd_min": None, "mjd_max": None}

    mean_ra = sum(r["ra"] for r in rows) / len(rows)
    mean_dec = sum(r["dec"] for r in rows) / len(rows)
    cos_dec = math.cos(math.radians(mean_dec))

    points = [
        {
            "d_ra": (r["ra"] - mean_ra) * cos_dec * 3600.0,
            "d_dec": (r["dec"] - mean_dec) * 3600.0,
            "mjd": r["mjd"],
            "band": r["band"],
            "identifier": r["identifier"],
            "has_stamp": r["has_stamp"],
        }
        for r in rows
    ]
    mjds = [p["mjd"] for p in points]
    return {
        "points": points,
        "n_points": len(points),
        "mean_ra": mean_ra,
        "mean_dec": mean_dec,
        "mjd_min": min(mjds),
        "mjd_max": max(mjds),
    }


async def get_coord_residuals(*, survey: str, oid: str) -> dict[str, Any]:
    cfg = SC(survey)
    raw = await alerce_client._get(cfg.lightcurve_url(oid))
    if not isinstance(raw, dict):
        raise ValueError(f"Unexpected lightcurve response shape: {type(raw).__name__}")
    return shape_coord_residuals(raw, survey=survey)
