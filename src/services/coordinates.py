"""RA/Dec formatting helpers.

Decimal degrees → HMS / DMS strings that match the conventions used by the
prototype's `raToHMS` / `decToDMS` (colon-separated, 3 decimals on RA seconds,
2 decimals on Dec seconds).
"""
from __future__ import annotations

import math


def ra_to_hms(ra_deg: float) -> str:
    h = ra_deg / 15.0
    hh = int(math.floor(h))
    mm_float = (h - hh) * 60.0
    mm = int(math.floor(mm_float))
    ss = (mm_float - mm) * 60.0
    return f"{hh:02d}:{mm:02d}:{ss:06.3f}"


def dec_to_dms(dec_deg: float) -> str:
    sign = "-" if dec_deg < 0 else "+"
    abs_d = abs(dec_deg)
    dd = int(math.floor(abs_d))
    am_float = (abs_d - dd) * 60.0
    am = int(math.floor(am_float))
    as_ = (am_float - am) * 60.0
    return f"{sign}{dd:02d}:{am:02d}:{as_:05.2f}"
