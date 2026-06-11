"""Robust statistics for forward candidate QC."""

from __future__ import annotations

import statistics
from typing import TypeVar

T = TypeVar("T")


def median_abs_deviation(values: list[float]) -> float:
    if not values:
        return 0.0
    med = statistics.median(values)
    return statistics.median(abs(v - med) for v in values)


def mad_z_scores(values: list[float]) -> list[float]:
    if len(values) < 2:
        return [0.0] * len(values)
    med = statistics.median(values)
    mad = median_abs_deviation(values)
    if mad == 0:
        return [0.0 if v == med else 99.0 for v in values]
    scale = 1.4826 * mad
    return [abs(v - med) / scale for v in values]


def filter_by_mad(
    items: list[T],
    values: list[float],
    *,
    threshold: float,
) -> tuple[list[T], list[T]]:
    """Return (kept, rejected) using MAD z-score on values."""
    if not items:
        return [], []
    if len(items) == 1:
        return items, []
    scores = mad_z_scores(values)
    kept, rejected = [], []
    for item, score in zip(items, scores, strict=True):
        (kept if score <= threshold else rejected).append(item)
    return kept, rejected


def weighted_mean(pairs: list[tuple[float, float]]) -> float:
    """pairs of (value, weight)."""
    total_w = sum(w for _, w in pairs)
    if total_w <= 0:
        raise ValueError("Total weight must be positive")
    return sum(v * w for v, w in pairs) / total_w
