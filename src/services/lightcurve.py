"""Lightcurve fetch + normalization.

Slice 4 scope: difference-flux detections only (no forced photometry, no
non-detections, no ZTF v2 mag_corr merge — those arrive in later slices).

Raw ALeRCE responses share the same envelope for LSST and ZTF v1:
  {"detections": [...], "non_detections": [...], "forced_photometry"?: [...]}

We run each detection through `normalize_det` (see services.normalize) which
gives us a common {mjd, band, psf_flux, e_psf_flux, mag, e_mag, candid, ...}
shape. This service then buckets by band and returns the minimum payload the
client chart needs.
"""
from __future__ import annotations

from typing import Any

from . import alerce_client
from .normalize import normalize_dets
from .survey_config import SC


def shape_lightcurve(raw: dict[str, Any], *, survey: str) -> dict[str, Any]:
    dets = raw.get("detections") or []
    normalized = normalize_dets(dets, survey)

    # Bucket by band. Drop rows missing mjd or flux (nothing to plot).
    bands: dict[str, list[dict[str, Any]]] = {}
    for d in normalized:
        if d.get("mjd") is None or d.get("psf_flux") is None:
            continue
        band = d.get("band") or "unknown"
        bands.setdefault(band, []).append(
            {
                "mjd": d["mjd"],
                "flux": d["psf_flux"],
                "e_flux": d.get("e_psf_flux"),
                "candid": d.get("candid"),
            }
        )

    # Order bands by the survey's canonical band ordering so legend entries
    # come out consistent (u,g,r,i,z,y on LSST; g,r,i on ZTF).
    cfg = SC(survey)
    ordered = [
        {"name": b, "points": sorted(bands[b], key=lambda p: p["mjd"])}
        for b in cfg.bands
        if b in bands
    ]
    # Append any unexpected bands at the end (e.g. 'unknown') so we don't drop data.
    for b, pts in bands.items():
        if b not in cfg.bands:
            ordered.append({"name": b, "points": sorted(pts, key=lambda p: p["mjd"])})

    return {"survey": survey, "bands": ordered, "n_det": sum(len(b["points"]) for b in ordered)}


async def get_lightcurve(*, survey: str, oid: str) -> dict[str, Any]:
    cfg = SC(survey)
    raw = await alerce_client._get(cfg.lightcurve_url(oid))
    if not isinstance(raw, dict):
        raise ValueError(f"Unexpected lightcurve response shape: {type(raw).__name__}")
    return shape_lightcurve(raw, survey=survey)
