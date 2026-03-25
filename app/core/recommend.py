from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.diagnosis import DiagnosisLabel
from app.core.scoring import ScoreBands
from app.models.domain import StudentTopicState


@dataclass(frozen=True)
class Recommendation:
    next_topic_id: str
    action: str
    rationale: list[str]
    suggested_question_ids: list[str]


def recommend_next(
    *,
    topic_id: str,
    diagnosis: object,
    topic_state: StudentTopicState,
    weakest_prereq_topic_id: Optional[str] = None,
    available_question_ids: Optional[list[str]] = None,
) -> Recommendation:
    """
    Minimal, demo-friendly recommendation policy.
    Returns a next action even if the graph is empty or there are no questions.
    """
    qids = available_question_ids or []
    bands = ScoreBands()
    mastery_band = bands.band(topic_state.mastery_score)

    label: DiagnosisLabel = getattr(diagnosis, "label", "direct_topic_weakness")

    if label == "prerequisite_gap" and weakest_prereq_topic_id:
        return Recommendation(
            next_topic_id=weakest_prereq_topic_id,
            action="practice_prerequisite",
            rationale=[
                "A prerequisite topic appears substantially weaker than the current topic.",
                f"Practice '{weakest_prereq_topic_id}' first, then retry the current topic.",
            ],
            suggested_question_ids=[],
        )

    if label in ("fragile_understanding", "confidence_issue"):
        return Recommendation(
            next_topic_id=topic_id,
            action="stabilize_understanding",
            rationale=[
                "You can sometimes get it right, but signals suggest the understanding is not stable yet.",
                "Do a short set of easier questions focusing on accuracy + confidence.",
            ],
            suggested_question_ids=qids[:3],
        )

    if label == "fluency_issue":
        return Recommendation(
            next_topic_id=topic_id,
            action="fluency_practice",
            rationale=[
                "Recent work is mostly correct but consistently slow.",
                "Do a short timed set with straightforward items to build speed.",
            ],
            suggested_question_ids=qids[:5],
        )

    if label == "transfer_issue":
        return Recommendation(
            next_topic_id=topic_id,
            action="transfer_practice",
            rationale=[
                "Direct practice seems okay, but transfer/word-problem performance is weaker.",
                "Practice a few word problems with clear steps and self-checks.",
            ],
            suggested_question_ids=qids[:3],
        )

    # direct_topic_weakness fallback
    if mastery_band == "weak":
        return Recommendation(
            next_topic_id=topic_id,
            action="practice_topic_basics",
            rationale=[
                "This topic looks weak right now.",
                "Practice fundamentals before moving on.",
            ],
            suggested_question_ids=qids[:5],
        )

    return Recommendation(
        next_topic_id=topic_id,
        action="continue_practice",
        rationale=[
            "No strong alternative signal; continue with the current topic.",
        ],
        suggested_question_ids=qids[:3],
    )

