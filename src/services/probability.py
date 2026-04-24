"""Radar-plot probability context.

ALeRCE's probability endpoint returns a flat list — one row per
(classifier_name, classifier_version, class_name). The UI wants a radar plot
per classifier+version, with a picker to swap between them client-side, so
we group here and let the template embed the whole payload as JSON.
"""
from __future__ import annotations

from typing import Any

from . import alerce_client
from .survey_config import SC


def _group_key(row: dict[str, Any]) -> str:
    name = row.get("classifier_name") or "?"
    version = row.get("classifier_version")
    return f"{name} v{version}" if version else name


def shape_probability_context(
    raw: Any, *, survey: str, classifier: str | None = None
) -> dict[str, Any]:
    """Group raw probability rows by classifier+version; pick a default.

    `classifier` is an optional override (as passed through from a deep-link
    URL) — when present, the group whose `classifier_name` matches wins the
    `default_key` slot, so the radar opens on the classifier the user linked
    to rather than the survey's default.

    Output:
      {
        "groups": [
          {"key": "lc_classifier v...", "classifier_name": "...",
           "classifier_version": "...",
           "classes": [{"class_name": "...", "probability": 0.42,
                         "is_max": bool}, ...]},
          ...
        ],
        "default_key": "<one of the keys>" or None,
      }
    """
    rows = raw if isinstance(raw, list) else []
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.get("class_name"):
            continue
        key = _group_key(row)
        group = by_key.setdefault(
            key,
            {
                "key": key,
                "classifier_name": row.get("classifier_name"),
                "classifier_version": row.get("classifier_version"),
                "classes": [],
            },
        )
        group["classes"].append(
            {
                "class_name": row["class_name"],
                "probability": row.get("probability"),
            }
        )

    groups: list[dict[str, Any]] = []
    for group in by_key.values():
        # Order classes within a group by descending probability so the radar
        # reads consistently between classifiers. Mark the max so the
        # renderer can highlight it.
        group["classes"].sort(key=lambda c: (c["probability"] or 0.0), reverse=True)
        if group["classes"]:
            top = group["classes"][0]["probability"]
            for c in group["classes"]:
                c["is_max"] = c["probability"] == top
        groups.append(group)

    # Default selection, in order of preference:
    #   1. explicit `classifier` override (from a deep-link URL)
    #   2. the survey's primary classifier
    #   3. the first group we see
    default_key: str | None = None
    if classifier:
        default_key = next(
            (g["key"] for g in groups if g["classifier_name"] == classifier), None
        )
    if default_key is None:
        default_name = SC(survey).default_classifier
        default_key = next(
            (g["key"] for g in groups if g["classifier_name"] == default_name), None
        )
    if default_key is None and groups:
        default_key = groups[0]["key"]

    return {"groups": groups, "default_key": default_key}


async def get_probability_context(
    *, survey: str, oid: str, classifier: str | None = None
) -> dict[str, Any]:
    cfg = SC(survey)
    raw = await alerce_client._get(cfg.prob_url(oid))
    return shape_probability_context(raw, survey=survey, classifier=classifier)
