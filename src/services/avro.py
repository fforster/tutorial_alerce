"""AVRO record metadata viewer.

ZTF alerts ship as AVRO records carrying per-detection metadata —
astrometry, instrumental fluxes, real-bogus scores, candidate-history
flags, etc. — plus the three image stamps. The stamps are already
rendered in the stamps panel; this service surfaces the *non-image*
fields so a user can inspect values like ``magpsf``, ``distnr``,
``magnr``, ``drb``, etc. without leaving the explorer.

The data comes from ``https://avro.alerce.online/get_avro_info`` (the
same host that serves the FITS stamps); LSST has no AVRO equivalent on
the public API, so ``get_avro_info`` returns ``available=False`` for
non-ZTF surveys and the modal renders an explanatory message rather
than an empty table.
"""
from __future__ import annotations

import logging
import math
from typing import Any

from . import alerce_client

log = logging.getLogger(__name__)

# ALeRCE-hosted AVRO metadata proxy. Same host as the stamp service.
AVRO_INFO_URL = "https://avro.alerce.online/get_avro_info"


def _format_value(v: Any) -> str:
    """Stringify an AVRO field for the table cell.

    Floats round to ~7 significant figures so columns line up; NaN/None
    surface as empty strings (the cell stays blank instead of printing
    "nan" or "None" verbatim). Booleans normalize to lowercase
    true/false, matching the AVRO spec.
    """
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        return f"{v:.7g}"
    return str(v)


def _shape_candidate(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Sort the candidate dict alphabetically and pre-format each value.

    Sorted client-side already, but we sort here so the *server-rendered*
    HTML is deterministic — matters for snapshot tests and for users who
    save the page.
    """
    return [
        {"name": k, "value": candidate[k], "value_display": _format_value(candidate[k])}
        for k in sorted(candidate.keys())
    ]


async def get_avro_info(
    *, oid: str, candid: str, survey: str
) -> dict[str, Any]:
    """Fetch the AVRO record for one ZTF detection and shape the
    ``candidate`` block into a flat (name, value) table.

    Failure modes — all surface as ``available=False`` with a human-
    readable ``reason`` so the modal can explain why the table is empty
    instead of showing a 500:
      - non-ZTF survey (LSST measurement_ids return 404 upstream)
      - upstream HTTP / network error
      - response wasn't a JSON object, or had no ``candidate`` block
    """
    if survey != "ztf":
        return {
            "available": False,
            "reason": (
                "AVRO records are only published for ZTF; "
                f"{(survey or 'this survey').upper()} "
                "does not expose them."
            ),
            "rows": [],
        }
    url = f"{AVRO_INFO_URL}?oid={oid}&candid={candid}"
    try:
        raw = await alerce_client._get(url)
    except Exception as e:
        log.warning("avro fetch failed (%s/%s): %s", oid, candid, e)
        return {
            "available": False,
            "reason": f"Upstream error: {e}",
            "rows": [],
        }
    if not isinstance(raw, dict):
        return {
            "available": False,
            "reason": "AVRO response was not a JSON object.",
            "rows": [],
        }
    candidate = raw.get("candidate") or {}
    object_id = raw.get("objectId")
    publisher = raw.get("publisher")
    schemavsn = raw.get("schemavsn")
    n_prv = len(raw.get("prv_candidates") or [])
    if not isinstance(candidate, dict) or not candidate:
        return {
            "available": False,
            "reason": "AVRO record carried no candidate data.",
            "rows": [],
            "object_id": object_id,
            "publisher": publisher,
            "schemavsn": schemavsn,
            "n_prv_candidates": n_prv,
        }
    return {
        "available": True,
        "rows": _shape_candidate(candidate),
        "object_id": object_id,
        "publisher": publisher,
        "schemavsn": schemavsn,
        "n_prv_candidates": n_prv,
    }
