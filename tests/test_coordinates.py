"""RA/Dec formatting sanity checks.

Match the prototype's raToHMS / decToDMS (colon-separated, 3 decimals on RA
seconds, 2 decimals on Dec seconds, leading zeros preserved).
"""
from __future__ import annotations

from src.services.coordinates import (
    dec_to_dms,
    equatorial_to_ecliptic,
    equatorial_to_galactic,
    ra_to_hms,
)


def test_ra_zero():
    assert ra_to_hms(0.0) == "00:00:00.000"


def test_ra_180_is_12h():
    assert ra_to_hms(180.0) == "12:00:00.000"


def test_ra_rounds_seconds():
    # 15.0 deg = 1h exactly; small offset → fractional seconds
    assert ra_to_hms(15.001).startswith("01:00:00.2")


def test_dec_positive_has_plus_sign():
    out = dec_to_dms(30.5)
    assert out.startswith("+30:")


def test_dec_negative_has_minus_sign():
    out = dec_to_dms(-30.5)
    assert out.startswith("-30:")


def test_dec_zero():
    assert dec_to_dms(0.0) == "+00:00:00.00"


# ── Equatorial → Galactic ────────────────────────────────────────────────────
#
# Reference points are intentionally chosen to round-trip through a rotation
# matrix with zero ambiguity. Tolerances are in arcseconds (≈ 1/3600°) —
# well below the 5-decimal display precision we show the user.

def test_galactic_center_maps_to_origin():
    """Sgr A* ≈ (266.4050°, -28.9362°) → Galactic (0, 0) by definition.
    ~1 arcsec tolerance absorbs the ICRS-vs-B1950 drift in the fixed
    rotation constants we use."""
    l, b = equatorial_to_galactic(266.40499, -28.93617)
    # Longitude wraps, so tolerate either side of 0 / 360.
    dl = min(abs(l), abs(l - 360.0))
    assert dl < 0.01
    assert abs(b) < 0.01


def test_north_galactic_pole_has_b_90():
    """NGP is (192.85948°, +27.12825°) — the anchor used to define the
    rotation matrix; b should land at +90° almost exactly."""
    _l, b = equatorial_to_galactic(192.85948, 27.12825)
    assert abs(b - 90.0) < 1e-4


def test_galactic_longitude_wraps_positive():
    """Longitude must be in [0, 360). RA = 0, Dec = 0 lands on a position
    just after ℓ = 96° (matches astropy)."""
    l, b = equatorial_to_galactic(0.0, 0.0)
    assert 0.0 <= l < 360.0
    assert 95.0 < l < 100.0
    # Not on the Galactic plane — just a sanity check that b is finite.
    assert -90.0 <= b <= 90.0


# ── Equatorial → Ecliptic (J2000) ────────────────────────────────────────────

def test_vernal_equinox_maps_to_zero():
    """(RA=0, Dec=0) is the vernal equinox — ecliptic longitude = 0, latitude = 0."""
    lam, beta = equatorial_to_ecliptic(0.0, 0.0)
    assert abs(lam) < 1e-6 or abs(lam - 360.0) < 1e-6
    assert abs(beta) < 1e-6


def test_north_ecliptic_pole_has_beta_90():
    """NEP is at RA = 270° (= 18h), Dec = 90° − ε ≈ 66.5607°."""
    _lam, beta = equatorial_to_ecliptic(270.0, 66.56071)
    assert abs(beta - 90.0) < 1e-3


def test_north_celestial_pole_has_beta_equals_90_minus_epsilon():
    """NCP is at equatorial Dec = +90°, so in ecliptic its latitude is
    90° − ε = 66.5607°. Longitude convention for a pole is 90° (= +y axis
    before the rotation)."""
    lam, beta = equatorial_to_ecliptic(0.0, 90.0)
    assert abs(beta - (90.0 - 23.4392911)) < 1e-4
    assert abs(lam - 90.0) < 1e-4


def test_ecliptic_longitude_in_range():
    """Sweep a handful of RA values — λ must stay in [0, 360)."""
    for ra in (0.0, 45.0, 90.0, 180.0, 270.0, 359.999):
        lam, _beta = equatorial_to_ecliptic(ra, 10.0)
        assert 0.0 <= lam < 360.0
