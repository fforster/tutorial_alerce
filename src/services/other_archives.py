"""External archive URL builders.

URL templates ported from the prototype's buildArchivesDropdown (~line 2693 of
alerce_explorer.html). The ALeRCE Explorer + Finding Chart links depend on the
survey + oid; everything else is RA/Dec conesearch.
"""
from __future__ import annotations

from typing import TypedDict
from urllib.parse import quote

from .coordinates import dec_to_dms, ra_to_hms


class ArchiveLink(TypedDict):
    name: str
    url: str


def build_archive_links(
    *, survey: str, oid: str, ra: float | None, dec: float | None
) -> list[ArchiveLink]:
    links: list[ArchiveLink] = []

    if survey == "ztf":
        alerce_url = f"https://alerce.online/object/{oid}"
    else:
        alerce_url = f"https://alerce.online/object/?oid={oid}&survey={survey}"
    links.append({"name": "ALeRCE Explorer", "url": alerce_url})

    if ra is None or dec is None:
        return links

    ra_hms_q = quote(ra_to_hms(ra))
    dec_dms_q = quote(dec_to_dms(dec))
    ra_dec = f"{ra}+{dec}"
    ra_dec_space = f"{ra}%20{dec}"

    links.extend([
        {
            "name": "DESI Legacy Survey DR11",
            "url": f"https://www.legacysurvey.org/viewer-dev/?ra={ra}&dec={dec}&layer=ls-dr11-early-v2&zoom=15",
        },
        {
            "name": "NED",
            "url": (
                "https://ned.ipac.caltech.edu/conesearch?search_type=Near%20Position%20Search"
                "&in_csys=Equatorial&in_equinox=J2000"
                f"&ra={ra_hms_q}&dec={dec_dms_q}&radius=0.17"
            ),
        },
        {
            "name": "PanSTARRS",
            "url": f"https://ps1images.stsci.edu/cgi-bin/ps1cutouts?pos={ra_dec}&filter=color",
        },
        {
            "name": "SDSS DR19",
            "url": f"https://skyserver.sdss.org/dr19/VisualTools/navi2?ra={ra}&dec={dec}",
        },
        {
            "name": "SIMBAD",
            "url": f"https://simbad.u-strasbg.fr/simbad/sim-coo?Coord={ra_dec_space}&Radius.unit=arcsec&Radius=10",
        },
        {
            "name": "TNS",
            "url": f"https://www.wis-tns.org/search?ra={ra}&decl={dec}&radius=10&coords_unit=arcsec",
        },
        {
            "name": "VizieR",
            "url": f"https://vizier.cds.unistra.fr/viz-bin/VizieR-4?-c={ra_dec}&-c.rs=10&-out.add=_r&-sort=_r&-out.max=4",
        },
        {
            "name": "VSX",
            "url": f"https://www.aavso.org/vsx/index.php?view=results.get&coords={ra_dec}&format=d&size=10&geom=r&unit=3&order=9",
        },
        {
            "name": "ALeRCE Finding Chart",
            "url": f"https://findingchart.alerce.online/get_chart?oid={oid}&candid=",
        },
    ])
    return links
