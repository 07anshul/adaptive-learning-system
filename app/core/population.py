from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.core.scoring import ScoringParams, clamp01, expected_time_seconds
from app.models.domain import Attempt, Question


@dataclass(frozen=True)
class PopulationUpdate:
    question_calibrated_difficulty: float
    topic_calibrated_difficulty: float


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _running_avg(prev_avg: float, prev_n: int, x: float) -> float:
    if prev_n <= 0:
        return float(x)
    return (prev_avg * prev_n + x) / float(prev_n + 1)


def observed_difficulty_from_aggregates(
    *,
    avg_correctness: float,
    avg_hints_used: float,
    avg_time_taken_seconds: float,
    expected_time_s: float,
) -> float:
    """
    Interpretable observed difficulty signal in [0,1]:
    - lower correctness -> harder
    - more hints -> harder
    - slower than expected -> harder
    """
    corr_term = clamp01(1.0 - avg_correctness)  # 0 easy, 1 hard
    hints_term = clamp01(avg_hints_used / 2.0)  # soft cap around 2
    if expected_time_s <= 1e-6:
        time_term = 0.0
    else:
        time_term = clamp01(avg_time_taken_seconds / expected_time_s)

    return clamp01(0.70 * corr_term + 0.20 * hints_term + 0.10 * time_term)


def calibrated_difficulty(
    *,
    prior: float,
    observed: float,
    prior_weight: float = 0.60,
) -> float:
    # Simple shrinkage toward prior for stability.
    return clamp01(prior_weight * clamp01(prior) + (1.0 - prior_weight) * clamp01(observed))

