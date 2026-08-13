"""Robust summaries and deterministic paired bootstrap intervals."""

from __future__ import annotations

import random
import statistics
from typing import Sequence


def median_mad(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        raise ValueError("at least one sample is required")
    center = statistics.median(values)
    return center, statistics.median(abs(value - center) for value in values)


def paired_bootstrap_ratio(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    samples: int = 10_000,
    seed: int = 0x43535632,
) -> tuple[float, float]:
    if not baseline or len(baseline) != len(candidate):
        raise ValueError("paired samples must be non-empty and equal in length")
    if samples < 100:
        raise ValueError("bootstrap requires at least 100 resamples")
    generator = random.Random(seed)
    ratios: list[float] = []
    count = len(baseline)
    for _ in range(samples):
        indices = [generator.randrange(count) for _ in range(count)]
        baseline_median = statistics.median(baseline[index] for index in indices)
        candidate_median = statistics.median(candidate[index] for index in indices)
        if baseline_median <= 0:
            raise ValueError("baseline samples must be positive")
        ratios.append(candidate_median / baseline_median)
    ratios.sort()
    return ratios[int(samples * 0.025)], ratios[min(samples - 1, int(samples * 0.975))]


def regression_threshold(comparison_noise: float, aa_noise: float) -> float:
    return max(0.05, comparison_noise, aa_noise)
