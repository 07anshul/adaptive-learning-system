from __future__ import annotations

"""
Deterministic blending between:
- population-level priors (calibrated difficulty)
- student-specific topic state (mastery/fragility/fluency)

Goal: population has more influence early; personal evidence dominates later.
No ML. No hidden behavior.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.core.scoring import clamp01
from app.models.domain import StudentTopicState


DEFAULT_EVIDENCE_THRESHOLD = 10  # demo-friendly; configurable per call


@dataclass(frozen=True)
class BlendWeights:
    personal_weight: float
    population_weight: float


@dataclass(frozen=True)
class PopulationExpectations:
    mastery: float
    fragility: float
    fluency: float


def compute_blend_weights(evidence_count: int, threshold: int = DEFAULT_EVIDENCE_THRESHOLD) -> BlendWeights:
    """
    Required shape:
      personal_weight = min(1.0, evidence_count/threshold)
      population_weight = 1.0 - personal_weight
    """
    th = max(1, int(threshold))
    pw = min(1.0, max(0.0, float(evidence_count) / float(th)))
    return BlendWeights(personal_weight=pw, population_weight=1.0 - pw)


def population_expectations_from_difficulty(calibrated_difficulty_0_1: float) -> PopulationExpectations:
    """
    Convert population difficulty (0 easy .. 1 hard) into expected student state baselines.
    These are simple, interpretable mappings used only as early-stage priors.
    """
    d = clamp01(calibrated_difficulty_0_1)
    # Easier topics start with higher expected mastery/fluency and lower fragility.
    mastery = clamp01(0.65 - 0.35 * d)
    fragility = clamp01(0.35 + 0.45 * d)
    fluency = clamp01(0.60 - 0.30 * d)
    return PopulationExpectations(mastery=mastery, fragility=fragility, fluency=fluency)


def blended_topic_state(
    personal: StudentTopicState,
    *,
    population_calibrated_difficulty: float,
    threshold: int = DEFAULT_EVIDENCE_THRESHOLD,
    now: Optional[datetime] = None,
) -> Tuple[StudentTopicState, BlendWeights, PopulationExpectations]:
    """
    Returns a *non-persisted* effective state used for decisions.
    Personal state remains the source of truth in storage.
    """
    w = compute_blend_weights(personal.evidence_count, threshold=threshold)
    pop = population_expectations_from_difficulty(population_calibrated_difficulty)

    ts = now or datetime.now(tz=timezone.utc)
    effective = StudentTopicState(
        student_id=personal.student_id,
        topic_id=personal.topic_id,
        mastery_score=clamp01(w.personal_weight * personal.mastery_score + w.population_weight * pop.mastery),
        fragility_score=clamp01(w.personal_weight * personal.fragility_score + w.population_weight * pop.fragility),
        fluency_score=clamp01(w.personal_weight * personal.fluency_score + w.population_weight * pop.fluency),
        evidence_count=personal.evidence_count,
        last_updated_at=ts,
    )
    return effective, w, pop

