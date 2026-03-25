from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

from app.core.diagnosis import DiagnosisLabel
from app.core.scoring import ScoreBands, clamp01
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


def _choose_similar_question(questions: List[Question], *, latest: Question) -> Optional[Question]:
    # Similar = same topic, low transfer, roughly similar difficulty.
    same_topic = [q for q in questions if q.topic_id == latest.topic_id]
    if not same_topic:
        return None
    candidates = [q for q in same_topic if q.transfer_load <= 0.30]
    if not candidates:
        candidates = same_topic
    candidates.sort(key=lambda q: (abs(q.difficulty_prior - latest.difficulty_prior), -q.diagnostic_value))
    return candidates[0] if candidates else None


def _choose_bridge_question(questions: List[Question], *, topic_id: str) -> Optional[Question]:
    # Bridge = moderate transfer and decent diagnostic value, not too hard.
    candidates = [q for q in questions if q.topic_id == topic_id]
    if not candidates:
        return None
    bridge = [
        q
        for q in candidates
        if 0.25 <= q.transfer_load <= 0.60 and q.difficulty_prior <= 0.70
    ]
    if not bridge:
        bridge = candidates
    bridge.sort(key=lambda q: (-q.diagnostic_value, q.difficulty_prior))
    return bridge[0] if bridge else None


def _choose_fluency_set(questions: List[Question], *, topic_id: str, k: int = 5) -> List[str]:
    # Fluency = low transfer, more procedural than conceptual, easy->medium.
    candidates = [q for q in questions if q.topic_id == topic_id]
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


def recommend_next_step(
    *,
    latest_attempt: Attempt,
    latest_question: Question,
    diagnosis_label: DiagnosisLabel,
    topic_state: StudentTopicState,
    prereq_topic_ids: List[str],
    topics_in_order: List[str],
    available_questions: List[Question],
) -> NextStepRecommendation:
    """
    Minimal next-step recommender using allowed actions only.
    Works even if prereq_topic_ids is empty (no edges).
    """
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
        qset = _choose_fluency_set(available_questions, topic_id=latest_question.topic_id, k=5)
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
            return NextStepRecommendation(
                action="show_hint_or_explanation",
                next_topic_id=latest_question.topic_id,
                question_id=latest_question.id,
                rationale=[
                    "Correctness may be shaky due to low confidence or hints used.",
                    "Show a short hint/explanation to stabilize understanding.",
                ],
                payload={
                    "hint_text": latest_question.hint_text,
                    "explanation_text": latest_question.explanation_text,
                },
            )
        bridge = _choose_bridge_question(available_questions, topic_id=latest_question.topic_id)
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
        similar = _choose_similar_question(available_questions, latest=latest_question)
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
        bridge = _choose_bridge_question(available_questions, topic_id=latest_question.topic_id)
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

    similar = _choose_similar_question(available_questions, latest=latest_question)
    return NextStepRecommendation(
        action="retry_similar_question",
        next_topic_id=latest_question.topic_id,
        question_id=similar.id if similar else None,
        rationale=[
            "No strong graph signal; defaulting to direct-topic practice.",
        ],
        payload={"similar_question_id": similar.id if similar else None},
    )

