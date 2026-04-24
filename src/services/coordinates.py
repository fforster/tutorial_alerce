"""RA/Dec formatting + coordinate-system rotations.

Decimal-degree → HMS / DMS strings that match the conventions used by the
prototype's `raToHMS` / `decToDMS` (colon-separated, 3 decimals on RA seconds,
2 decimals on Dec seconds).

`equatorial_to_galactic` and `equatorial_to_ecliptic` are pure-Python
matrix rotations — no astropy dependency. Accuracy is well under the
display precision we use (5 decimal degrees ≈ 36 mas); for the Basic
Information panel the J2000 vs ICRS distinction doesn't matter.
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


# ICRS → Galactic rotation matrix.
#
# Uses the values in the IAU/ESA 1997 convention (Murray 1989):
#   α_NGP = 192.85948°, δ_NGP = 27.12825°, ℓ_CP = 122.93192°
#
# Constant matrix computed once at import. Sanity-checked by the unit tests:
# the Galactic Center ≈ (266.405°, −28.936°) maps to (ℓ, b) ≈ (0, 0), and
# the NGP ≈ (192.85948°, 27.12825°) maps to b ≈ 90°.
_R_ICRS_TO_GAL: tuple[tuple[float, float, float], ...] = (
    (-0.0548755604162154, -0.8734370902348850, -0.4838350155487132),
    ( 0.4941094278755837, -0.4448296299600112,  0.7469822444972189),
    (-0.8676661490190047, -0.1980763734312015,  0.4559837761750669),
)


# IAU 2006 obliquity at J2000 (23° 26' 21.448" = 23.4392911°). Good to
# better than a milliarcsec — far finer than our 5-decimal display.
_ECLIPTIC_OBLIQUITY_DEG = 23.4392911


def _ll_bb_from_vec(x: float, y: float, z: float) -> tuple[float, float]:
    """Unit vector → (longitude, latitude) in degrees, longitude in [0, 360)."""
    lat = math.degrees(math.asin(max(-1.0, min(1.0, z))))
    lon = math.degrees(math.atan2(y, x))
    if lon < 0:
        lon += 360.0
    return lon, lat


def equatorial_to_galactic(ra_deg: float, dec_deg: float) -> tuple[float, float]:
    """ICRS (ra, dec) in degrees → Galactic (l, b) in degrees.

    l is wrapped into [0, 360); b is in [-90, 90]. Raises nothing — callers
    are expected to validate finite inputs upstream (we do that in
    shape_object_info so the template sees None rather than NaN).
    """
    ra = math.radians(ra_deg)
    dec = math.radians(dec_deg)
    cd = math.cos(dec)
    x = cd * math.cos(ra)
    y = cd * math.sin(ra)
    z = math.sin(dec)
    r0, r1, r2 = _R_ICRS_TO_GAL
    xp = r0[0] * x + r0[1] * y + r0[2] * z
    yp = r1[0] * x + r1[1] * y + r1[2] * z
    zp = r2[0] * x + r2[1] * y + r2[2] * z
    return _ll_bb_from_vec(xp, yp, zp)


def equatorial_to_ecliptic(ra_deg: float, dec_deg: float) -> tuple[float, float]:
    """ICRS (ra, dec) in degrees → J2000 ecliptic (λ, β) in degrees.

    Single rotation about the X-axis by the mean obliquity ε (no precession
    or nutation — we're aligning to J2000, not to the date). λ in [0, 360);
    β in [-90, 90].
    """
    eps = math.radians(_ECLIPTIC_OBLIQUITY_DEG)
    ra = math.radians(ra_deg)
    dec = math.radians(dec_deg)
    cd = math.cos(dec)
    x = cd * math.cos(ra)
    y = cd * math.sin(ra)
    z = math.sin(dec)
    ce, se = math.cos(eps), math.sin(eps)
    xp = x
    yp = ce * y + se * z
    zp = -se * y + ce * z
    return _ll_bb_from_vec(xp, yp, zp)
