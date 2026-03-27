from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

from app.core.diagnosis import DiagnosisLabel
from app.core.scoring import ScoringParams, ScoreBands, clamp01, expected_time_seconds
from app.models.domain import Attempt, Question, StudentTopicState


NextStepAction = Literal[
    "retry_similar_question",
    "review_prerequisite_topic",
    "show_hint_or_explanation",
    "assign_bridge_question",
    "assign_fluency_practice",
    "advance_to_next_topic",
]


@dataclass(frozen=True)
class NextStepRecommendation:
    action: NextStepAction
    next_topic_id: Optional[str]
    question_id: Optional[str]
    rationale: List[str]
    payload: dict


def _choose_similar_question(
    questions: List[Question],
    *,
    latest: Question,
    avoid_question_id: Optional[str] = None,
    prefer_easier: bool = False,
) -> Optional[Question]:
    # Similar = same topic, low transfer, roughly similar difficulty.
    # Avoid immediate repetition when alternatives exist.
    same_topic = [q for q in questions if q.topic_id == latest.topic_id]
    if not same_topic:
        return None
    filtered = [q for q in same_topic if q.id != avoid_question_id] if avoid_question_id else same_topic
    pool = filtered or same_topic  # allow same only if no alternatives
    candidates = [q for q in pool if q.transfer_load <= 0.30]
    if not candidates:
        candidates = pool
    if prefer_easier:
        # Prefer easier/lower-transfer after wrong attempts.
        candidates.sort(
            key=lambda q: (
                q.difficulty_prior,
                q.transfer_load,
                abs(q.difficulty_prior - latest.difficulty_prior),
                -q.diagnostic_value,
            )
        )
    else:
        candidates.sort(key=lambda q: (abs(q.difficulty_prior - latest.difficulty_prior), q.transfer_load, -q.diagnostic_value))
    return candidates[0] if candidates else None


def _choose_bridge_question(
    questions: List[Question],
    *,
    topic_id: str,
    avoid_question_id: Optional[str] = None,
) -> Optional[Question]:
    # Bridge = moderate transfer and decent diagnostic value, not too hard.
    candidates = [q for q in questions if q.topic_id == topic_id]
    if not candidates:
        return None
    filtered = [q for q in candidates if q.id != avoid_question_id] if avoid_question_id else candidates
    use_candidates = filtered or candidates
    bridge = [
        q
        for q in use_candidates
        if 0.25 <= q.transfer_load <= 0.60 and q.difficulty_prior <= 0.70
    ]
    if not bridge:
        bridge = use_candidates
    bridge.sort(key=lambda q: (-q.diagnostic_value, q.difficulty_prior))
    return bridge[0] if bridge else None


def _choose_fluency_set(
    questions: List[Question],
    *,
    topic_id: str,
    k: int = 5,
    avoid_question_id: Optional[str] = None,
) -> List[str]:
    # Fluency = low transfer, more procedural than conceptual, easy->medium.
    candidates = [q for q in questions if q.topic_id == topic_id]
    if avoid_question_id:
        filtered = [q for q in candidates if q.id != avoid_question_id]
        candidates = filtered or candidates
    candidates = [
        q
        for q in candidates
        if q.transfer_load <= 0.25 and q.conceptual_load <= 0.45
    ] or candidates
    candidates.sort(key=lambda q: (q.difficulty_prior, -q.procedural_load, -q.diagnostic_value))
    return [q.id for q in candidates[:k]]


def _is_consistently_strong(latest_attempt: Attempt, state: StudentTopicState) -> bool:
    # Simple, interpretable "strong" gate.
    return (
        state.evidence_count >= 5
        and state.mastery_score >= 0.75
        and state.fluency_score >= 0.65
        and state.fragility_score <= 0.35
        and latest_attempt.correctness is True
        and latest_attempt.hints_used == 0
        and latest_attempt.confidence_rating >= 4
    )


def _is_clean_success(att: Attempt, q: Question) -> bool:
    """
    Demo-friendly "clean success":
    - correct
    - no hints
    - high confidence
    - not slow relative to expected time
    """
    if not att.correctness:
        return False
    if int(att.hints_used) != 0:
        return False
    if int(att.confidence_rating) < 4:
        return False
    exp = expected_time_seconds(q, ScoringParams())
    if exp <= 1e-6:
        return True
    # Allow "reasonable" time: not exceeding ~expected time.
    return (float(att.time_taken_seconds) / exp) <= 1.05


def _recent_clean_rate(
    recent_attempts: Optional[List[Attempt]],
    *,
    question_by_id: dict[str, Question],
    window: int = 6,
) -> float:
    """
    Fraction of attempts in the last `window` that are "clean successes".
    Deterministic, interpretable, and uses per-question expected time when available.
    """
    if not recent_attempts:
        return 0.0
    tail = recent_attempts[-window:] if len(recent_attempts) > window else recent_attempts
    if not tail:
        return 0.0
    clean_n = 0
    for a in tail:
        q = question_by_id.get(a.question_id)
        if q is None:
            # Conservative fallback (no time normalization): correct + no hints + high confidence.
            if a.correctness and int(a.hints_used) == 0 and int(a.confidence_rating) >= 4:
                clean_n += 1
            continue
        if _is_clean_success(a, q):
            clean_n += 1
    return clean_n / float(len(tail))


def _recent_correct_rate(recent_attempts: Optional[List[Attempt]], window: int = 6) -> float:
    if not recent_attempts:
        return 0.0
    tail = recent_attempts[-window:] if len(recent_attempts) > window else recent_attempts
    if not tail:
        return 0.0
    return sum(1 for a in tail if a.correctness) / float(len(tail))


def _recent_sample_n(recent_attempts: Optional[List[Attempt]], window: int = 6) -> int:
    if not recent_attempts:
        return 0
    tail = recent_attempts[-window:] if len(recent_attempts) > window else recent_attempts
    return len(tail)


def _readiness_score(state: StudentTopicState) -> float:
    """
    Interpretable readiness score from state only (0..1).
    Higher mastery + higher fluency + lower fragility => higher readiness.
    """
    m = clamp01(float(state.mastery_score))
    f = clamp01(float(state.fluency_score))
    fr = clamp01(float(state.fragility_score))
    return clamp01(0.55 * m + 0.25 * f + 0.20 * (1.0 - fr))


def _choose_progression_question(
    questions: List[Question],
    *,
    latest: Question,
    avoid_question_id: Optional[str],
) -> Optional[Question]:
    """
    After a clean streak, prefer a different question that is:
    - same topic
    - not easier than the latest (roughly)
    - optionally slightly higher transfer or difficulty
    """
    same = [q for q in questions if q.topic_id == latest.topic_id]
    if avoid_question_id:
        filtered = [q for q in same if q.id != avoid_question_id]
    else:
        filtered = same
    pool = filtered or same
    if not pool:
        return None
    # Prefer equal-or-harder and a bit more transfer (still capped).
    cand = [q for q in pool if q.difficulty_prior >= (latest.difficulty_prior - 0.05)]
    cand = cand or pool
    cand.sort(key=lambda q: (-q.difficulty_prior, -q.transfer_load, -q.diagnostic_value))
    return cand[0] if cand else None


def recommend_next_step(
    *,
    latest_attempt: Attempt,
    latest_question: Question,
    diagnosis_label: DiagnosisLabel,
    topic_state: StudentTopicState,
    prereq_topic_ids: List[str],
    topics_in_order: List[str],
    available_questions: List[Question],
    recent_attempts: Optional[List[Attempt]] = None,
) -> NextStepRecommendation:
    """
    Minimal next-step recommender using allowed actions only.
    Works even if prereq_topic_ids is empty (no edges).
    """
    # 0) Demo-friendly progression without hard-coded streak cliffs:
    # If recent evidence is strong, stop recommending easier/remedial questions.
    # This uses a readiness score (state) + a recent clean-success boost.
    q_by_id = {q.id: q for q in available_questions}
    clean_rate = _recent_clean_rate(recent_attempts, question_by_id=q_by_id, window=6)
    correct_rate = _recent_correct_rate(recent_attempts, window=6)
    n_recent = _recent_sample_n(recent_attempts, window=6)
    readiness = _readiness_score(topic_state)
    # Boost only when the latest attempt is correct; a new failure should remove the boost.
    # Scale boost by sample size so we don't overreact after 1 clean attempt.
    sample_scale = min(1.0, n_recent / 3.0)
    recent_boost = (0.18 * clean_rate + 0.10 * correct_rate) * sample_scale if latest_attempt.correctness else 0.0
    effective_readiness = clamp01(readiness + recent_boost)

    # If the student looks ready, advance to next topic; otherwise choose a non-easier progression question.
    if latest_attempt.correctness and n_recent >= 3 and (effective_readiness >= 0.70 or (clean_rate >= 0.80 and correct_rate >= 0.80)):
        next_topic = None
        if latest_question.topic_id in topics_in_order:
            i = topics_in_order.index(latest_question.topic_id)
            if i + 1 < len(topics_in_order):
                next_topic = topics_in_order[i + 1]
        if next_topic is not None:
            return NextStepRecommendation(
                action="advance_to_next_topic",
                next_topic_id=next_topic,
                question_id=None,
                rationale=[
                    "Recent performance is clean and consistent.",
                    "Advance to keep momentum.",
                ],
                payload={
                    "from_topic_id": latest_question.topic_id,
                    "readiness": round(effective_readiness, 3),
                    "recent_clean_rate": round(clean_rate, 3),
                    "recent_n": int(n_recent),
                },
            )

    if latest_attempt.correctness and n_recent >= 2 and (clean_rate >= 0.50 or effective_readiness >= 0.55):
        prog = _choose_progression_question(
            available_questions,
            latest=latest_question,
            avoid_question_id=latest_question.id,
        )
        return NextStepRecommendation(
            action="retry_similar_question",
            next_topic_id=latest_question.topic_id,
            question_id=prog.id if prog else None,
            rationale=[
                "Recent performance is improving.",
                "Use a different same-topic question (not easier) to confirm stability.",
            ],
            payload={
                "readiness": round(effective_readiness, 3),
                "recent_clean_rate": round(clean_rate, 3),
                "recent_n": int(n_recent),
                "progression_question_id": prog.id if prog else None,
            },
        )

    # 1) Strong performance can advance (only if it's truly strong)
    if _is_consistently_strong(latest_attempt, topic_state):
        # next topic = next in curated order; if not found, stay.
        next_topic = None
        if latest_question.topic_id in topics_in_order:
            i = topics_in_order.index(latest_question.topic_id)
            if i + 1 < len(topics_in_order):
                next_topic = topics_in_order[i + 1]
        return NextStepRecommendation(
            action="advance_to_next_topic",
            next_topic_id=next_topic,
            question_id=None,
            rationale=[
                "Performance is consistently strong (high mastery + good fluency + low fragility).",
                "Advance to the next topic to keep momentum.",
            ],
            payload={"from_topic_id": latest_question.topic_id},
        )

    # 2) Diagnosis-driven rules
    if diagnosis_label == "prerequisite_gap" and prereq_topic_ids:
        # Choose the first prereq in weighted order (repo already orders by edge weight)
        prereq = prereq_topic_ids[0]
        return NextStepRecommendation(
            action="review_prerequisite_topic",
            next_topic_id=prereq,
            question_id=None,
            rationale=[
                "A prerequisite topic appears weaker than the current topic.",
                "Review the prerequisite before retrying this topic.",
            ],
            payload={"prerequisite_topic_id": prereq, "current_topic_id": latest_question.topic_id},
        )

    if diagnosis_label == "fluency_issue":
        qset = _choose_fluency_set(
            available_questions,
            topic_id=latest_question.topic_id,
            k=5,
            avoid_question_id=latest_question.id,
        )
        return NextStepRecommendation(
            action="assign_fluency_practice",
            next_topic_id=latest_question.topic_id,
            question_id=qset[0] if qset else None,
            rationale=[
                "Work is mostly correct but slow.",
                "Assign short, low-transfer practice to build speed and reduce effort.",
            ],
            payload={"question_ids": qset},
        )

    if diagnosis_label == "fragile_understanding":
        # If hints/low confidence already present, show explanation; otherwise bridge question.
        if latest_attempt.hints_used >= 1 or latest_attempt.confidence_rating <= 2:
            follow_up = _choose_similar_question(
                available_questions,
                latest=latest_question,
                avoid_question_id=latest_question.id,
                prefer_easier=(not latest_attempt.correctness),
            )
            return NextStepRecommendation(
                action="show_hint_or_explanation",
                next_topic_id=latest_question.topic_id,
                question_id=follow_up.id if follow_up else latest_question.id,
                rationale=[
                    "Correctness may be shaky due to low confidence or hints used.",
                    "Show a short hint/explanation to stabilize understanding.",
                ],
                payload={
                    "hint_text": latest_question.hint_text,
                    "explanation_text": latest_question.explanation_text,
                    "follow_up_question_id": follow_up.id if follow_up else latest_question.id,
                },
            )
        bridge = _choose_bridge_question(
            available_questions,
            topic_id=latest_question.topic_id,
            avoid_question_id=latest_question.id,
        )
        return NextStepRecommendation(
            action="assign_bridge_question",
            next_topic_id=latest_question.topic_id,
            question_id=bridge.id if bridge else None,
            rationale=[
                "Understanding looks fragile.",
                "Assign a bridge question that connects steps and meaning.",
            ],
            payload={"bridge_question_id": bridge.id if bridge else None},
        )

    if diagnosis_label == "direct_topic_weakness":
        similar = _choose_similar_question(
            available_questions,
            latest=latest_question,
            avoid_question_id=latest_question.id,
            prefer_easier=(not latest_attempt.correctness),
        )
        return NextStepRecommendation(
            action="retry_similar_question",
            next_topic_id=latest_question.topic_id,
            question_id=similar.id if similar else None,
            rationale=[
                "The current topic looks weak right now.",
                "Retry a similar, lower-transfer question to rebuild accuracy.",
            ],
            payload={"similar_question_id": similar.id if similar else None},
        )

    # 3) Tie-break / fallbacks when graph evidence is weak or no edges exist
    # If wrong + transfer heavy => bridge question; otherwise retry similar.
    if (not latest_attempt.correctness) and latest_question.transfer_load >= 0.60:
        bridge = _choose_bridge_question(
            available_questions,
            topic_id=latest_question.topic_id,
            avoid_question_id=latest_question.id,
        )
        return NextStepRecommendation(
            action="assign_bridge_question",
            next_topic_id=latest_question.topic_id,
            question_id=bridge.id if bridge else None,
            rationale=[
                "Missed a high-transfer question.",
                "Use a bridge question to connect the concept to the application.",
            ],
            payload={"bridge_question_id": bridge.id if bridge else None},
        )

    similar = _choose_similar_question(
        available_questions,
        latest=latest_question,
        avoid_question_id=latest_question.id,
        prefer_easier=(not latest_attempt.correctness),
    )
    return NextStepRecommendation(
        action="retry_similar_question",
        next_topic_id=latest_question.topic_id,
        question_id=similar.id if similar else None,
        rationale=[
            "No strong graph signal; defaulting to direct-topic practice.",
        ],
        payload={"similar_question_id": similar.id if similar else None},
    )

