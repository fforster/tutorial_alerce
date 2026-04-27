"""TNS classification lookup via ALeRCE's htmx bridge.

The ALeRCE production stack exposes an htmx endpoint that resolves (ra, dec)
to a TNS object and returns a tiny HTML fragment with type/name/redshift
plus a link to the TNS page. We proxy it server-side (the repo-wide rule:
the browser never calls ALeRCE directly) and parse the three table cells
into a plain dict so the template can render them in our own theme —
embedding ALeRCE's stylesheet inline would clash with the Basic Information
panel's Tailwind classes.

The endpoint 200s with an empty table body when the cone-search hits nothing;
we return None in that case so the template skips the TNS row entirely.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import httpx

log = logging.getLogger(__name__)

TNS_HTMX_URL = "https://api.alerce.online/v2/object_details/htmx/tns/"
# Keep the timeout tighter than the main API (30s) — TNS is a nice-to-have,
# not worth blocking the Basic Information panel if the bridge is slow.
_TIMEOUT = httpx.Timeout(10.0)

# Capture the text between <td id="type">…</td> (and name/redshift). The
# production fragment puts ids on those three cells specifically, so we key
# on the id rather than cell order.
_CELL_RE = re.compile(r'id="(?P<id>type|name|redshift)"[^>]*>(?P<val>[^<]*)</td>')
_LINK_RE = re.compile(r'id="tns-link"[^>]*href="(?P<url>[^"]+)"')


def _maybe_float(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_tns_fragment(html: str) -> dict[str, Any] | None:
    """Pull type/name/redshift/url out of the ALeRCE TNS htmx fragment.

    Returns None when the fragment has no object (empty tbody) — the caller
    uses that to hide the TNS row instead of rendering a blank table.
    """
    cells = {m.group("id"): m.group("val").strip() for m in _CELL_RE.finditer(html)}
    name = cells.get("name") or None
    if not name:
        return None
    link_m = _LINK_RE.search(html)
    url = link_m.group("url") if link_m else f"https://www.wis-tns.org/object/{name}"
    return {
        "type": cells.get("type") or None,
        "name": name,
        "redshift": _maybe_float(cells.get("redshift")),
        "url": url,
    }


async def get_tns_info(*, ra: float | None, dec: float | None) -> dict[str, Any] | None:
    """Fetch + parse the ALeRCE TNS bridge. None on missing coords or any
    upstream/network failure — TNS is strictly additive, never fatal."""
    if ra is None or dec is None:
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            r = await client.get(TNS_HTMX_URL, params={"ra": ra, "dec": dec})
            r.raise_for_status()
            return parse_tns_fragment(r.text)
    except Exception as e:
        log.warning("TNS htmx fetch failed (ra=%s, dec=%s): %s", ra, dec, e)
        return None
