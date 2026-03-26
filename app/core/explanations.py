from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.diagnosis import DiagnosisLabel
from app.core.next_step import NextStepAction
from app.core.scoring import ScoreBands
from app.models.domain import StudentTopicState


def _mastery_band(state: StudentTopicState) -> str:
    return ScoreBands().band(state.mastery_score)


def _fragility_level(state: StudentTopicState) -> str:
    # Demo-friendly thresholds; keep consistent with UI label behavior.
    if state.fragility_score >= 0.60:
        return "high"
    return "moderate"


def explain_diagnosis(
    *,
    diagnosis_label: DiagnosisLabel,
    topic_state: StudentTopicState,
    topic_title: Optional[str] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Deterministic, short, teacher-friendly explanation.
    Uses only diagnosis label + topic state (+ optional evidence/titles).
    """
    title = topic_title or topic_state.topic_id
    mastery_band = _mastery_band(topic_state)
    fragility_level = _fragility_level(topic_state)

    ev = evidence or {}

    if diagnosis_label == "prerequisite_gap":
        prereq_id = ev.get("weakest_prereq_topic_id")
        prereq_part = f" ({prereq_id})" if prereq_id else ""
        return (
            f"The student may be struggling with prerequisite concepts{prereq_part} "
            f"rather than the current topic directly ({title})."
        )

    if diagnosis_label == "fragile_understanding":
        reasons = ev.get("reasons")
        # Deterministic phrasing: prefer evidence reasons when present.
        if isinstance(reasons, list) and reasons:
            if "low_confidence" in reasons and "hints_used" in reasons:
                return "The student is often correct here, but low confidence and hint use suggest fragile understanding."
            if "slow" in reasons and ("low_confidence" in reasons or "hints_used" in reasons):
                return "The student can sometimes get it right, but speed and confidence suggest fragile understanding."
            if "slow" in reasons:
                return "The student is often correct here, but slow performance suggests fragile understanding."
            if "hints_used" in reasons:
                return "The student is often correct here, but hint use suggests fragile understanding."
        return "The student is often correct here, but speed and confidence suggest fragile understanding."

    if diagnosis_label == "fluency_issue":
        return "The student is often correct here, but speed suggests a fluency issue rather than a missing concept."

    if diagnosis_label == "transfer_issue":
        return "The student seems comfortable with direct practice but struggles when the concept appears in word problems."

    if diagnosis_label == "confidence_issue":
        return "The student’s correctness seems inconsistent with low confidence, suggesting uncertainty even when they sometimes get the right answer."

    # direct_topic_weakness fallback
    if mastery_band == "weak":
        return f"The student may be developing fundamentals in this topic ({title})."
    # If mastery isn't low but label says direct weakness, use fragility hint.
    if fragility_level == "high":
        return f"Understanding in this topic ({title}) seems unstable right now."
    return f"The student may be struggling with this topic ({title}) for reasons that are not clearly prereq-related."


def explain_recommendation(
    *,
    recommendation_action: NextStepAction,
    diagnosis_label: DiagnosisLabel,
    topic_state: StudentTopicState,
    next_topic_title: Optional[str] = None,
    hint_text: Optional[str] = None,
) -> str:
    """
    Deterministic, short explanation for the next recommendation action.
    """
    next_title = next_topic_title or ""
    if recommendation_action == "review_prerequisite_topic":
        return "Review the prerequisite topic first, then try the current topic again."

    if recommendation_action == "assign_bridge_question":
        return "Use a bridge question to connect steps to the meaning of the concept."

    if recommendation_action == "show_hint_or_explanation":
        return "A short hint/explanation should help stabilize understanding—then retry a similar problem."

    if recommendation_action == "assign_fluency_practice":
        return "Do a short timed set of easier practice to build speed and reduce effort."

    if recommendation_action == "retry_similar_question":
        return "Retry with a similar (lower-transfer) question to rebuild accuracy and confidence."

    if recommendation_action == "advance_to_next_topic":
        return "Performance is strong and stable; it’s a good time to move to the next topic."

    # Fallback (shouldn’t happen with allowed actions)
    return f"Next step: {recommendation_action}."

