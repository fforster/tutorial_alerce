"""Survey abstraction — LSST and ZTF differ in API base URLs, field names,
and band sets. All survey-specific logic lives here; never branch on the survey
string in callers — extend this config instead.

Mirrors the SURVEY_CONFIG / SC() pattern from ../ALeRCE_explorer/alerce_explorer.html.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class SurveyConfig:
    name: str
    api_base: str
    bands: tuple[str, ...]
    default_classifier: str
    has_forced_phot: bool
    has_science_flux: bool
    # Fitzpatrick (1999) R_lambda per band (Milky Way extinction).
    extinction_r: dict[str, float] = field(default_factory=dict)
    # Mutates a dict of query params to match the survey's API naming.
    extra_params: Callable[[dict[str, object]], dict[str, object]] = lambda p: p


def _ztf_extra_params(params: dict[str, object]) -> dict[str, object]:
    out = {k: v for k, v in params.items() if v is not None and k != "survey"}
    if "class_name" in out:
        out["class"] = out.pop("class_name")
    if "n_det" in out:
        out["ndet"] = out.pop("n_det")
    out.setdefault("ranking", 1)
    return out


def _lsst_extra_params(params: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in params.items() if v is not None}


SURVEY_CONFIG: dict[str, SurveyConfig] = {
    "lsst": SurveyConfig(
        name="lsst",
        api_base="https://api.alerce.online/lsst/v1",
        bands=("u", "g", "r", "i", "z", "y"),
        default_classifier="lc_classifier_top",
        has_forced_phot=False,
        has_science_flux=False,
        extinction_r={
            "u": 4.145, "g": 3.237, "r": 2.273,
            "i": 1.684, "z": 1.323, "y": 1.088,
        },
        extra_params=_lsst_extra_params,
    ),
    "ztf": SurveyConfig(
        name="ztf",
        api_base="https://api.alerce.online/ztf/v1",
        bands=("g", "r", "i"),
        default_classifier="lc_classifier",
        has_forced_phot=True,
        has_science_flux=True,
        extinction_r={"g": 3.237, "r": 2.273, "i": 1.684},
        extra_params=_ztf_extra_params,
    ),
}


def SC(survey: str) -> SurveyConfig:
    try:
        return SURVEY_CONFIG[survey]
    except KeyError as e:
        raise ValueError(f"Unknown survey: {survey!r}") from e
