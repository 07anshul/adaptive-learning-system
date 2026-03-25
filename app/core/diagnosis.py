from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Optional

from app.core.scoring import ScoreBands, clamp01
from app.models.domain import Attempt, Question, StudentTopicState


DiagnosisLabel = Literal[
    "direct_topic_weakness",
    "prerequisite_gap",
    "fragile_understanding",
    "fluency_issue",
    "transfer_issue",
    "confidence_issue",
]


@dataclass(frozen=True)
class Diagnosis:
    label: DiagnosisLabel
    summary: str
    evidence: dict[str, object]


@dataclass(frozen=True)
class DiagnosisParams:
    # Score thresholds
    weak_max: float = 0.40
    okay_max: float = 0.70

    # "Substantially weaker prereq" threshold (mastery gap)
    prereq_gap_delta: float = 0.18
    prereq_weak_max: float = 0.45

    # Fragile signals
    slow_ratio_for_fragile: float = 1.4  # time_taken / expected_time
    low_confidence_max: int = 2
    hints_for_fragile: int = 1

    # Fluency detection (across recent attempts)
    fluency_window: int = 8
    fluency_min_correct_rate: float = 0.70
    fluency_slow_ratio: float = 1.3

    # Transfer issue
    transfer_high_min: float = 0.60
    transfer_low_max: float = 0.25
    transfer_window: int = 12
    transfer_min_samples_each: int = 3
    transfer_failure_delta: float = 0.30  # high-transfer correct rate lower by this much

    # Confidence issue
    confidence_window: int = 10
    confidence_low_max: int = 2
    confidence_fluctuation_min: float = 0.35  # correctness rate between [0.35,0.65] implies fluctuation


def _expected_time_seconds(q: Question) -> float:
    # Keep consistent with scoring module (duplicate lightly to avoid circular import complexity)
    load = clamp01(0.4 * q.conceptual_load + 0.4 * q.procedural_load + 0.2 * q.transfer_load)
    return 25.0 + 45.0 * clamp01(q.difficulty_prior) + 35.0 * load


def _is_slow(attempt: Attempt, question: Question, *, ratio: float) -> bool:
    exp = _expected_time_seconds(question)
    if exp <= 1e-6:
        return False
    return (attempt.time_taken_seconds / exp) >= ratio


def _correct_rate(attempts: Iterable[Attempt]) -> Optional[float]:
    a = list(attempts)
    if not a:
        return None
    return sum(1 for x in a if x.correctness) / float(len(a))


def _avg_time_ratio(attempts: Iterable[Attempt], questions: dict[str, Question]) -> Optional[float]:
    ratios: list[float] = []
    for att in attempts:
        q = questions.get(att.question_id)
        if q is None:
            continue
        exp = _expected_time_seconds(q)
        if exp > 1e-6:
            ratios.append(att.time_taken_seconds / exp)
    if not ratios:
        return None
    return sum(ratios) / float(len(ratios))


def _confidence_is_low(att: Attempt, params: DiagnosisParams) -> bool:
    return int(att.confidence_rating) <= params.low_confidence_max


def _topic_band(state: StudentTopicState, params: DiagnosisParams) -> str:
    return ScoreBands(weak_max=params.weak_max, okay_max=params.okay_max).band(state.mastery_score)


def diagnose_attempt(
    *,
    attempt: Attempt,
    question: Question,
    topic_state: StudentTopicState,
    prereq_states: Optional[list[StudentTopicState]] = None,
    recent_attempts: Optional[list[Attempt]] = None,
    recent_questions: Optional[dict[str, Question]] = None,
    params: Optional[DiagnosisParams] = None,
) -> Diagnosis:
    """
    Rule-based diagnosis (explainable, no ML).

    Inputs:
    - prereq_states: states for prerequisite topics (can be empty/None if no edges)
    - recent_attempts/recent_questions: optional history for fluency/transfer/confidence patterns

    Works even with no graph edges by falling back to direct-topic / attempt-based signals.
    """
    p = params or DiagnosisParams()
    prereqs = prereq_states or []
    history = recent_attempts or []
    q_by_id = recent_questions or {}

    topic_mastery = float(topic_state.mastery_score)
    topic_fragility = float(topic_state.fragility_score)
    topic_fluency = float(topic_state.fluency_score)

    topic_is_weak = topic_mastery <= p.weak_max
    topic_is_okay_or_better = topic_mastery > p.weak_max

    # --- Rule A: prerequisite_gap (only meaningful if we have prereq states) ---
    # If attempt is wrong OR topic is weak, and some prerequisite is substantially weaker.
    if prereqs:
        weakest = min(prereqs, key=lambda s: s.mastery_score)
        gap = topic_mastery - float(weakest.mastery_score)
        prereq_is_weak = float(weakest.mastery_score) <= p.prereq_weak_max
        if (not attempt.correctness or topic_is_weak) and prereq_is_weak and gap >= p.prereq_gap_delta:
            return Diagnosis(
                label="prerequisite_gap",
                summary=f"Likely prerequisite gap: '{weakest.topic_id}' appears weaker than the current topic.",
                evidence={
                    "current_topic_id": topic_state.topic_id,
                    "current_mastery": round(topic_mastery, 3),
                    "weakest_prereq_topic_id": weakest.topic_id,
                    "weakest_prereq_mastery": round(float(weakest.mastery_score), 3),
                    "mastery_gap": round(gap, 3),
                },
            )

    # --- Rule B: fragile_understanding (correct but shaky) ---
    # Correct but slow OR low confidence OR hints => fragile label.
    if attempt.correctness:
        slow = _is_slow(attempt, question, ratio=p.slow_ratio_for_fragile)
        low_conf = _confidence_is_low(attempt, p)
        hinty = int(attempt.hints_used) >= p.hints_for_fragile
        if slow or low_conf or hinty:
            reasons = []
            if slow:
                reasons.append("slow")
            if low_conf:
                reasons.append("low_confidence")
            if hinty:
                reasons.append("hints_used")
            return Diagnosis(
                label="fragile_understanding",
                summary=f"Correct, but signs of fragility ({', '.join(reasons)}).",
                evidence={
                    "current_topic_id": topic_state.topic_id,
                    "mastery": round(topic_mastery, 3),
                    "fragility": round(topic_fragility, 3),
                    "fluency": round(topic_fluency, 3),
                    "reasons": reasons,
                    "time_taken_seconds": int(attempt.time_taken_seconds),
                    "hints_used": int(attempt.hints_used),
                    "confidence_rating": int(attempt.confidence_rating),
                },
            )

    # --- Rule C: transfer_issue (direct/low-transfer OK but high-transfer failing) ---
    # Uses question.transfer_load and recent history (if available).
    if history and q_by_id:
        window = history[-p.transfer_window :]
        hi = [a for a in window if (q := q_by_id.get(a.question_id)) and q.transfer_load >= p.transfer_high_min]
        lo = [a for a in window if (q := q_by_id.get(a.question_id)) and q.transfer_load <= p.transfer_low_max]
        if len(hi) >= p.transfer_min_samples_each and len(lo) >= p.transfer_min_samples_each:
            hi_rate = _correct_rate(hi) or 0.0
            lo_rate = _correct_rate(lo) or 0.0
            if (lo_rate - hi_rate) >= p.transfer_failure_delta and not attempt.correctness and question.transfer_load >= p.transfer_high_min:
                return Diagnosis(
                    label="transfer_issue",
                    summary="Struggles appear stronger on transfer/word problems than on direct practice.",
                    evidence={
                        "current_topic_id": topic_state.topic_id,
                        "high_transfer_correct_rate": round(hi_rate, 3),
                        "low_transfer_correct_rate": round(lo_rate, 3),
                        "question_transfer_load": round(float(question.transfer_load), 3),
                        "window_n": len(window),
                    },
                )

    # --- Rule D: fluency_issue (mostly correct but slow across similar problems) ---
    if history and q_by_id:
        window = history[-p.fluency_window :]
        rate = _correct_rate(window)
        avg_ratio = _avg_time_ratio(window, q_by_id)
        if rate is not None and avg_ratio is not None:
            if rate >= p.fluency_min_correct_rate and avg_ratio >= p.fluency_slow_ratio:
                return Diagnosis(
                    label="fluency_issue",
                    summary="Mostly correct recently, but consistently slow (fluency issue).",
                    evidence={
                        "current_topic_id": topic_state.topic_id,
                        "recent_correct_rate": round(rate, 3),
                        "avg_time_ratio_vs_expected": round(avg_ratio, 3),
                        "window_n": len(window),
                    },
                )

    # --- Rule E: confidence_issue (fluctuating correctness + low confidence) ---
    if history:
        window = history[-p.confidence_window :]
        rate = _correct_rate(window)
        low_conf_frac = sum(1 for a in window if int(a.confidence_rating) <= p.confidence_low_max) / float(len(window)) if window else 0.0
        if rate is not None:
            fluctuating = p.confidence_fluctuation_min <= rate <= (1.0 - p.confidence_fluctuation_min)
            if fluctuating and low_conf_frac >= 0.50:
                return Diagnosis(
                    label="confidence_issue",
                    summary="Correctness is fluctuating and confidence is frequently low.",
                    evidence={
                        "current_topic_id": topic_state.topic_id,
                        "recent_correct_rate": round(rate, 3),
                        "low_confidence_fraction": round(low_conf_frac, 3),
                        "window_n": len(window),
                    },
                )

    # --- Rule F: direct_topic_weakness (fallback/default) ---
    # If topic is weak and prereqs are not especially weaker (or no prereq info), attribute directly.
    if topic_is_weak:
        return Diagnosis(
            label="direct_topic_weakness",
            summary="Current topic appears weak based on mastery and this attempt.",
            evidence={
                "current_topic_id": topic_state.topic_id,
                "mastery": round(topic_mastery, 3),
                "fragility": round(topic_fragility, 3),
                "fluency": round(topic_fluency, 3),
                "attempt_correct": bool(attempt.correctness),
            },
        )

    # If topic isn't weak and no stronger rule fired, choose the closest short explanation.
    if not attempt.correctness and topic_is_okay_or_better and question.transfer_load >= p.transfer_high_min:
        return Diagnosis(
            label="transfer_issue",
            summary="This looks like a transfer/word-problem miss rather than a basic skill miss.",
            evidence={
                "current_topic_id": topic_state.topic_id,
                "mastery": round(topic_mastery, 3),
                "question_transfer_load": round(float(question.transfer_load), 3),
            },
        )

    return Diagnosis(
        label="direct_topic_weakness",
        summary="No strong graph/history signal; interpreting as direct topic difficulty for now.",
        evidence={
            "current_topic_id": topic_state.topic_id,
            "mastery": round(topic_mastery, 3),
            "attempt_correct": bool(attempt.correctness),
        },
    )

