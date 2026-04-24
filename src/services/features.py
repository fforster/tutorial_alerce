"""Feature-table fetch + normalization.

The ALeRCE features endpoint returns a flat list of
  {"name": str, "value": number|null, "fid": int|null, ...}
rows. We normalize each row into the shape the template expects:
  {"name": str, "band": str|"—", "value_display": str}

Band mapping is driven off SurveyConfig.bands so we can add LSST later
without branching on survey in the caller. ZTF's fids map 1→g, 2→r, 3→i
and 12 → "multi" (the multiband features). None / 0 / other fids show as
"—".
"""
from __future__ import annotations

import logging
import math
from typing import Any

from . import alerce_client
from .survey_config import SC

log = logging.getLogger(__name__)


# ZTF's band-fid convention. 12 is the per-object multiband aggregate
# (e.g. Multiband_period), not a real band; surface it with a distinct
# label so the table filter can group by it.
_ZTF_FID_TO_BAND = {1: "g", 2: "r", 3: "i", 12: "multi"}


def pick_default_version(versions: list[str]) -> str | None:
    """Pick the canonical "latest" feature-extractor version.

    The ZTF features endpoint bundles every version ever run on an object
    (~5 versions); there's no metadata marking which one is current. We
    prefer versions that match the strict `N.N.N` scheme (three pure-integer
    dot-separated segments, e.g. "27.5.6"), sorted by (first, second, third)
    DESC — so `27.5.6` beats `27.5.0` beats `25.0.0`, and all beat the old
    `lc_classifier_1.2.1-P` labels or partial versions like `25.0.1a8` whose
    third segment isn't a pure number. Versions that fail the strict match
    are excluded from the ranking; when nothing matches we fall back to
    insertion order (the API appends newest last, so the last entry is the
    freshest we can identify).

    This is shared between the features-table modal (default selected
    version) and the light-curve fold-period extractor, so the user never
    sees the table display one Multiband_period while folding uses another
    (the original ZTF20acuwouz bug).
    """
    if not versions:
        return None
    ranked: list[tuple[int, int, int, str]] = []
    for v in versions:
        parts = v.split(".")
        if len(parts) < 3:
            continue
        try:
            # Strict: all three segments must be pure integers. "1a8" fails
            # int() and the version falls through to the last-seen fallback.
            first, second, third = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        ranked.append((first, second, third, v))
    if ranked:
        ranked.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        return ranked[0][3]
    return versions[-1]


def _band_label(fid: Any, survey: str) -> str:
    """Turn a numeric fid into a display string. Unknown/missing → '—'."""
    if fid is None:
        return "—"
    try:
        fid_int = int(fid)
    except (TypeError, ValueError):
        return "—"
    if survey == "ztf":
        return _ZTF_FID_TO_BAND.get(fid_int, "—")
    # LSST: if we ever wire up features, map integer band index to the
    # canonical band letter via SurveyConfig.bands (0-indexed).
    cfg = SC(survey)
    if 0 <= fid_int < len(cfg.bands):
        return cfg.bands[fid_int]
    return "—"


def _format_value(v: Any) -> str:
    """Readable display for a single feature value.

    Numeric values render with up to 6 significant figures (trailing-zero
    stripped); NaN and None render as "—" so the filter input can match
    them as a group. Strings pass through.
    """
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        if isinstance(v, float) and math.isnan(v):
            return "—"
        if isinstance(v, float):
            # 6 sig figs, trim trailing zeros so "0.100000" reads as "0.1".
            s = f"{v:.6g}"
            return s
        return str(v)
    return str(v)


def shape_features(raw: Any, *, survey: str) -> dict[str, Any]:
    """Normalize the raw feature list into the shape the template expects.

    The ZTF endpoint bundles *every* extractor version the object has ever
    been processed with into one response (~5 versions × ~180 rows each).
    We keep every row but tag it with its `version` string, expose the
    versions list for a client-side picker, and default to the *last*
    version seen in the response — the ALeRCE API appends newest-last for
    classifiers and the prototype relies on the same convention.

    Rows are sorted by (version, band, name) so within a version the
    bands read as contiguous g/r/i/multi blocks. Non-dict entries are
    skipped silently — we don't want a single malformed row to black-hole
    the whole table.
    """
    if not isinstance(raw, list):
        return {
            "rows": [], "versions": [], "n_by_version": {},
            "bands": [], "default_version": None, "n": 0,
        }
    rows: list[dict[str, Any]] = []
    versions_seen: list[str] = []
    versions_set: set[str] = set()
    for r in raw:
        if not isinstance(r, dict):
            continue
        name = r.get("name")
        if not isinstance(name, str) or not name:
            continue
        version = r.get("version") or "—"
        if version not in versions_set:
            versions_set.add(version)
            versions_seen.append(version)
        rows.append(
            {
                "name": name,
                "band": _band_label(r.get("fid"), survey),
                "value_display": _format_value(r.get("value")),
                "version": version,
            }
        )
    # Primary sort: version (kept in first-seen order so the select maps
    # onto the API's "append newest last" convention); then band so g/r/i
    # group within a version; then name. "—" sorts last (U+2014 > ASCII).
    version_order = {v: i for i, v in enumerate(versions_seen)}
    rows.sort(key=lambda x: (version_order[x["version"]], x["band"], x["name"]))
    counts: dict[str, int] = {v: 0 for v in versions_seen}
    for r in rows:
        counts[r["version"]] += 1
    # Distinct bands in canonical order: survey bands first (g, r, i, …),
    # then "multi" (ZTF's multiband aggregate), then "—" (unknown). Bands
    # that don't appear in any row are omitted so the select doesn't offer
    # dead options for this object.
    seen_bands = {r["band"] for r in rows}
    cfg = SC(survey)
    canonical = list(cfg.bands) + ["multi", "—"]
    bands = [b for b in canonical if b in seen_bands]
    # Any unexpected band labels (shouldn't happen, but defensive) land at
    # the end in insertion order so they still show up in the picker.
    for b in seen_bands - set(canonical):
        bands.append(b)
    return {
        "rows": rows,
        "versions": versions_seen,
        "n_by_version": counts,
        "bands": bands,
        # Pick the "latest" version via the shared pattern-aware helper so
        # the light-curve Fold button and this modal agree on which version's
        # Multiband_period to use.
        "default_version": pick_default_version(versions_seen),
        "n": len(rows),
    }


# ── Parametric-fit overlays on the light curve ──────────────────────────────
#
# Three of the ALeRCE ZTF feature-extractor outputs are *parametric fits* of
# the light curve, each producing a handful of per-band numbers:
#
#   SPM  (Sánchez-Sáez+2021 stochastic-parametric model) —
#        SPM_A, SPM_beta, SPM_t0, SPM_gamma, SPM_tau_rise, SPM_tau_fall (+SPM_chi)
#   FLEET (mag-space exp+linear model) —
#        fleet_a, fleet_w, fleet_m0, fleet_t0 (+fleet_chi)
#   TDE tail (late-time t^-5/12-style decay, in mag) —
#        TDE_mag0, TDE_decay (+TDE_decay_chi)
#
# The extractor emits them as ordinary rows in the features list tagged with a
# fid + version. For the light-curve overlay we want the same "latest version"
# policy that drives the features-table modal and the fold-period (via
# `pick_default_version`), so that the displayed parameters can't drift away
# from what the Show-features modal would render for the same object.
#
# The extracted bundle has shape:
#   {
#     "spm":   {"g": {"A":..., "beta":..., ...}, "r": {...}, ...},
#     "fleet": {"g": {"a":..., "w":..., ...}, ...},
#     "tde":   {"g": {"mag0":..., "decay":..., ...}, ...},
#   }
# A band is included only when ALL required params are finite; an overlay key
# is present only when at least one band survived. The client uses this both
# to drive the dropdown (hide options that have no data) and to compute the
# model traces.
_PARAMETRIC_FITS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    # (overlay_key, required_params, optional_params)
    ("spm",
     ("SPM_A", "SPM_beta", "SPM_t0", "SPM_gamma", "SPM_tau_rise", "SPM_tau_fall"),
     ("SPM_chi",)),
    ("fleet",
     ("fleet_a", "fleet_w", "fleet_m0", "fleet_t0"),
     ("fleet_chi",)),
    ("tde",
     ("TDE_mag0", "TDE_decay"),
     ("TDE_decay_chi",)),
)


def _finite_float(v: Any) -> float | None:
    """Return v as float when finite (rejects None, NaN, strings, inf)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f


def extract_parametric_fits(raw: Any, *, survey: str) -> dict[str, dict[str, dict[str, float]]]:
    """Pull the SPM / FLEET / TDE-tail parametric fits out of a features list.

    Uses `pick_default_version` so the overlay always mirrors the version
    shown in the features-table modal. A band's params are only emitted when
    every required field is finite — partial fits don't draw a broken curve.

    Returns {} when the features list is missing, wrong shape, or carries no
    recognizable parametric fit. The light-curve template hides the overlay
    picker in that case.
    """
    if not isinstance(raw, list):
        return {}
    # Collect versions + per-version per-band params in one pass. We don't
    # know upfront which overlay / band we'll keep, so bucket everything
    # and prune at the end.
    versions_seen: list[str] = []
    versions_set: set[str] = set()
    # version → feature_name → band → value
    by_version: dict[str, dict[str, dict[str, float]]] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name:
            continue
        version = row.get("version") or "—"
        if version not in versions_set:
            versions_set.add(version)
            versions_seen.append(version)
        v = _finite_float(row.get("value"))
        if v is None:
            continue
        band = _band_label(row.get("fid"), survey)
        # Parametric fits are per-band; rows with unknown / multi bands
        # (fid=12 / None) can't land in a per-band overlay.
        if band in ("—", "multi"):
            continue
        by_version.setdefault(version, {}).setdefault(name, {})[band] = v

    chosen = pick_default_version(versions_seen)
    if chosen is None:
        return {}
    version_map = by_version.get(chosen, {})

    out: dict[str, dict[str, dict[str, float]]] = {}
    for overlay_key, required, optional in _PARAMETRIC_FITS:
        per_band: dict[str, dict[str, float]] = {}
        # Union of bands seen across any of this overlay's features; we still
        # filter to "all required present" below.
        candidate_bands: set[str] = set()
        for fname in required + optional:
            candidate_bands.update(version_map.get(fname, {}).keys())
        for band in candidate_bands:
            params: dict[str, float] = {}
            missing = False
            for fname in required:
                v = version_map.get(fname, {}).get(band)
                if v is None:
                    missing = True
                    break
                # Strip the feature-name prefix (SPM_A → A) so the client
                # doesn't need to re-derive the short name. Matches the
                # structure used by the reference overlay code.
                params[fname.split("_", 1)[1] if "_" in fname else fname] = v
            if missing:
                continue
            for fname in optional:
                v = version_map.get(fname, {}).get(band)
                if v is not None:
                    params[fname.split("_", 1)[1] if "_" in fname else fname] = v
            per_band[band] = params
        if per_band:
            out[overlay_key] = per_band
    return out


async def get_features(*, survey: str, oid: str) -> dict[str, Any]:
    """Fetch + shape the feature table for an object.

    Returns `{available: bool, rows: [...], n: int}`. `available=False`
    means the survey doesn't expose features in the REST API (LSST today);
    the caller should render a "not available" message rather than an
    empty table. Upstream errors propagate so the route can render a red
    error banner.
    """
    cfg = SC(survey)
    url = cfg.features_url(oid)
    if url is None:
        return {
            "available": False,
            "rows": [], "versions": [], "n_by_version": {},
            "bands": [], "default_version": None, "n": 0,
        }
    raw = await alerce_client._get(url)
    return {"available": True, **shape_features(raw, survey=survey)}
