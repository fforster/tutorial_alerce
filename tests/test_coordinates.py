"""RA/Dec formatting sanity checks.

Match the prototype's raToHMS / decToDMS (colon-separated, 3 decimals on RA
seconds, 2 decimals on Dec seconds, leading zeros preserved).
"""
from __future__ import annotations

from src.services.coordinates import dec_to_dms, ra_to_hms


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
