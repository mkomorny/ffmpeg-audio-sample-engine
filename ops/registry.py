"""Aggregates every op module into one flat list + category grouping for the UI."""

from __future__ import annotations

from typing import Any

from ops import convert, effects, generators, pitch_time, trim_levels

CATEGORY_ORDER = [
    trim_levels.CATEGORY,
    convert.CATEGORY,
    pitch_time.CATEGORY,
    effects.CATEGORY,
    generators.CATEGORY,
]

ALL_OPS: list[dict[str, Any]] = [
    *trim_levels.OPS,
    *convert.OPS,
    *pitch_time.OPS,
    *effects.OPS,
    *generators.OPS,
]

OPS_BY_ID: dict[str, dict[str, Any]] = {op["id"]: op for op in ALL_OPS}


def grouped() -> list[tuple[str, list[dict[str, Any]]]]:
    """Ops grouped by category, in CATEGORY_ORDER, preserving each category's own order."""
    return [
        (category, [op for op in ALL_OPS if op["category"] == category])
        for category in CATEGORY_ORDER
    ]
