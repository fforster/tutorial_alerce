"""64-bit-integer-safe JSON parsing.

LSST object IDs exceed 2**53 and lose precision under standard JSON decoding.
We wrap any bare integer of >=16 digits in quotes before parsing so it becomes
a string; compare such IDs as strings everywhere downstream.
"""
from __future__ import annotations

import json
import re
from typing import Any

_BIG_INT = re.compile(rb"([:,\[]\s*)(-?\d{16,})(?=\s*[,\]\}])")


def safe_json_loads(raw: str | bytes) -> Any:
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    wrapped = _BIG_INT.sub(rb'\1"\2"', data)
    return json.loads(wrapped)
