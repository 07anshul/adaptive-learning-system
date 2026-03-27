from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.models.domain import Attempt, Question, StudentTopicState


def clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


@dataclass(frozen=True)
class ScoreBands:
    weak_max: float = 0.40
    okay_max: float = 0.70

    def band(self, score_0_1: float) -> str:
        s = clamp01(score_0_1)
        if s <= self.weak_max:
            return "weak"
        if s <= self.okay_max:
            return "okay"
        return "strong"


@dataclass(frozen=True)
class ScoringParams:
    """
    Simple, interpretable parameters (no ML):
    - Scores are clamped to [0, 1]
    - mastery: "how likely they can do it"
    - fluency: "how fast/effortless"
    - fragility: "how unstable / not-yet-solid" (higher = more fragile)
    """

    # Evidence-based step size: early attempts move more than later ones.
    base_lr: float = 0.18
    min_lr: float = 0.04

    # Attempt-feature normalization
    hints_soft_cap: int = 2  # 0,1,2 have most of the meaning; >2 saturates

    # Expected-time baseline: scales with difficulty + cognitive load.
    expected_time_base_s: float = 25.0
    expected_time_diff_s: float = 45.0  # added at difficulty_prior=1
    expected_time_load_s: float = 35.0  # added at load=1

    # Mastery delta weights (sum-ish ~1)
    mastery_w_correct: float = 1.00
    mastery_w_conf: float = 0.25
    mastery_w_speed: float = 0.20
    mastery_w_hints: float = 0.35

    # Fluency delta weights
    fluency_w_correct: float = 0.65
    fluency_w_speed: float = 0.55
    fluency_w_hints: float = 0.40

    # Fragility delta weights (note: fragility goes DOWN on clean success)
    fragility_w_wrong: float = 0.65
    fragility_w_low_conf: float = 0.35
    fragility_w_slow: float = 0.35
    fragility_w_hints: float = 0.40
    fragility_clean_success_drop: float = 0.55


def compute_cognitive_load(q: Question) -> float:
    # Interpretable blend: conceptual + procedural matter most; transfer a bit less.
    return clamp01(0.4 * q.conceptual_load + 0.4 * q.procedural_load + 0.2 * q.transfer_load)


def expected_time_seconds(q: Question, params: ScoringParams) -> float:
    load = compute_cognitive_load(q)
    return (
        params.expected_time_base_s
        + params.expected_time_diff_s * clamp01(q.difficulty_prior)
        + params.expected_time_load_s * load
    )


def normalize_speed(time_taken_s: int, q: Question, params: ScoringParams) -> float:
    """
    Returns speed_score in [-1, +1]:
    +1 = very fast for this question
     0 = about expected time
    -1 = very slow for this question
    """
    exp = expected_time_seconds(q, params)
    if exp <= 1e-6:
        return 0.0
    ratio = float(time_taken_s) / exp  # 1.0 = expected
    # Piecewise, interpretable:
    # - ratio <= 0.6 => fast => +1
    # - ratio == 1.0 => 0
    # - ratio >= 1.8 => slow => -1
    if ratio <= 0.6:
        return 1.0
    if ratio >= 1.8:
        return -1.0
    if ratio < 1.0:
        # map [0.6,1.0] -> [1,0]
        return (1.0 - ratio) / (1.0 - 0.6)
    # map [1.0,1.8] -> [0,-1]
    return -(ratio - 1.0) / (1.8 - 1.0)


def normalize_confidence(confidence_rating_1_5: int) -> float:
    """
    Returns conf_score in [-1, +1]:
    1 -> -1 (very low)
    3 ->  0 (neutral)
    5 -> +1 (very high)
    """
    c = int(confidence_rating_1_5)
    return clamp((c - 3) / 2.0, -1.0, 1.0)


def normalize_hints(hints_used: int, params: ScoringParams) -> float:
    """
    Returns hint_score in [0, 1] where 1 = very hint-heavy.
    """
    cap = max(1, int(params.hints_soft_cap))
    return clamp(float(hints_used) / cap, 0.0, 1.0)


def lr_from_evidence(evidence_count: int, params: ScoringParams) -> float:
    # Simple diminishing step size: 0 attempts => base_lr, then shrinks.
    lr = params.base_lr / (1.0 + 0.12 * max(0, evidence_count))
    return clamp(lr, params.min_lr, params.base_lr)


@dataclass(frozen=True)
class ScoreUpdate:
    prev: StudentTopicState
    new: StudentTopicState
    mastery_delta: float
    fluency_delta: float
    fragility_delta: float
    features: dict[str, float]


def default_state(student_id: str, topic_id: str, now: Optional[datetime] = None) -> StudentTopicState:
    ts = now or datetime.now(tz=timezone.utc)
    return StudentTopicState(
        student_id=student_id,
        topic_id=topic_id,
        mastery_score=0.35,
        fragility_score=0.50,
        fluency_score=0.35,
        evidence_count=0,
        last_updated_at=ts,
    )


def update_student_topic_state(
    prev: Optional[StudentTopicState],
    *,
    attempt: Attempt,
    question: Question,
    params: Optional[ScoringParams] = None,
    now: Optional[datetime] = None,
) -> ScoreUpdate:
    """
    Interpretable scoring update based only on attempt + question fields.
    Works even if topic has no edges (graph not required).
    """
    p = params or ScoringParams()
    ts = now or attempt.submitted_at
    prev_state = prev or default_state(attempt.student_id, attempt.topic_id, now=ts)

    speed = normalize_speed(attempt.time_taken_seconds, question, p)  # [-1,1]
    conf = normalize_confidence(attempt.confidence_rating)  # [-1,1]
    hints = normalize_hints(attempt.hints_used, p)  # [0,1]
    load = compute_cognitive_load(question)  # [0,1]
    diff = clamp01(question.difficulty_prior)  # [0,1]

    # Weight: harder + heavier-load questions are more informative per attempt.
    # Keep mild so we don't overreact.
    info_weight = 0.85 + 0.25 * diff + 0.15 * load  # ~[0.85,1.25]

    lr = lr_from_evidence(prev_state.evidence_count, p) * info_weight

    # --- mastery update ---
    # Correctness is primary; confidence/speed nudge; hints reduce effective gain.
    if attempt.correctness:
        mastery_signal = (
            p.mastery_w_correct
            + p.mastery_w_conf * conf
            + p.mastery_w_speed * speed
            - p.mastery_w_hints * hints
        )
        # Demo-friendly: repeated "clean success" should move mastery noticeably.
        clean = (
            clamp01((speed + 1.0) / 2.0) * clamp01((conf + 1.0) / 2.0) * (1.0 - hints)
        )
        mastery_gain = 0.10 + 0.06 * clean  # up to +60% on very clean attempts
        mastery_delta = lr * mastery_gain * mastery_signal
    else:
        mastery_signal = (
            -p.mastery_w_correct
            - 0.15 * (1.0 - conf)  # low confidence makes wrong more diagnostic
            - 0.10 * hints
        )
        mastery_delta = lr * 0.12 * mastery_signal

    # --- fluency update ---
    # Fluency is mostly about speed + low hints, and still needs correctness.
    if attempt.correctness:
        fluency_signal = (
            p.fluency_w_correct
            + p.fluency_w_speed * speed
            - p.fluency_w_hints * hints
        )
        clean = (
            clamp01((speed + 1.0) / 2.0) * clamp01((conf + 1.0) / 2.0) * (1.0 - hints)
        )
        fluency_gain = 0.10 + 0.05 * clean
        fluency_delta = lr * fluency_gain * fluency_signal
    else:
        fluency_signal = (
            -0.70
            - 0.25 * (1.0 - speed)  # slow+wrong hurts fluency more
            - 0.20 * hints
        )
        fluency_delta = lr * 0.11 * fluency_signal

    # --- fragility update ---
    # Fragility rises when performance looks unstable: wrong, slow, low-confidence, hint-heavy.
    # It drops on "clean success": correct, fast-ish, confident, no hints.
    low_conf = clamp01((3 - attempt.confidence_rating) / 2.0)  # 1 at conf=1, 0 at conf>=3
    slow = clamp01((-speed + 1.0) / 2.0)  # speed=-1 ->1, speed=+1 ->0

    if attempt.correctness:
        clean = (
            clamp01((speed + 1.0) / 2.0)  # fast ->1
            * clamp01((conf + 1.0) / 2.0)  # high conf ->1
            * (1.0 - hints)
        )
        # Demo-friendly: clean success should reduce fragility more strongly.
        fragility_delta = -lr * (0.10 + 0.06 * clean) * p.fragility_clean_success_drop * clean

        # But correct-yet-shaky should still increase fragility a bit.
        shaky = 0.55 * low_conf + 0.45 * slow + 0.60 * hints
        fragility_delta += lr * 0.06 * shaky
    else:
        fragility_signal = (
            p.fragility_w_wrong
            + p.fragility_w_low_conf * low_conf
            + p.fragility_w_slow * slow
            + p.fragility_w_hints * hints
        )
        fragility_delta = lr * 0.10 * fragility_signal

    new_state = StudentTopicState(
        student_id=prev_state.student_id,
        topic_id=prev_state.topic_id,
        mastery_score=clamp01(prev_state.mastery_score + mastery_delta),
        fragility_score=clamp01(prev_state.fragility_score + fragility_delta),
        fluency_score=clamp01(prev_state.fluency_score + fluency_delta),
        evidence_count=prev_state.evidence_count + 1,
        last_updated_at=ts,
    )

    return ScoreUpdate(
        prev=prev_state,
        new=new_state,
        mastery_delta=new_state.mastery_score - prev_state.mastery_score,
        fluency_delta=new_state.fluency_score - prev_state.fluency_score,
        fragility_delta=new_state.fragility_score - prev_state.fragility_score,
        features={
            "lr": lr,
            "difficulty_prior": diff,
            "cognitive_load": load,
            "speed_score": speed,
            "confidence_score": conf,
            "hints_score": hints,
        },
    )

