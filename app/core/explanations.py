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
        return f"This looks more like a prerequisite gap{prereq_part} than a direct issue in {title}."

    if diagnosis_label == "fragile_understanding":
        reasons = ev.get("reasons")
        # Deterministic phrasing: prefer evidence reasons when present.
        if isinstance(reasons, list) and reasons:
            if "low_confidence" in reasons and "hints_used" in reasons:
                return "The student was correct, but low confidence and hint use suggest fragile understanding."
            if "slow" in reasons and ("low_confidence" in reasons or "hints_used" in reasons):
                return "The student was correct, but the response still looks fragile because of speed/confidence."
            if "slow" in reasons:
                return "The student was correct, but slower work suggests fragile understanding."
            if "hints_used" in reasons:
                return "The student was correct, but heavy hint use suggests fragile understanding."
        return "The student was correct, but the response still looks fragile because of speed/confidence."

    if diagnosis_label == "fluency_issue":
        return "This looks more like a fluency issue: mostly correct, but too slow."

    if diagnosis_label == "transfer_issue":
        return "Direct practice looks better than transfer/word-problem use right now."

    if diagnosis_label == "confidence_issue":
        return "Accuracy and confidence are out of sync; confidence looks like the limiting factor."

    # direct_topic_weakness fallback
    if mastery_band == "weak":
        return f"This looks like a direct difficulty with {title}, not a clear prerequisite gap."
    # If mastery isn't low but label says direct weakness, use fragility hint.
    if fragility_level == "high":
        return f"Understanding in {title} looks unstable right now."
    return f"This looks like a direct difficulty with {title}, not a clear prerequisite gap."


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
        return "Review the prerequisite first, then return to this topic."

    if recommendation_action == "assign_bridge_question":
        return "A bridge question is the best next step before advancing."

    if recommendation_action == "show_hint_or_explanation":
        return "Use a short hint/explanation, then try a different similar question."

    if recommendation_action == "assign_fluency_practice":
        return "Use short, lower-load practice to build speed and consistency."

    if recommendation_action == "retry_similar_question":
        return "A similar lower-transfer question is a better next step before advancing."

    if recommendation_action == "advance_to_next_topic":
        return "Performance looks stable here, so moving to the next topic is reasonable."

    # Fallback (shouldn’t happen with allowed actions)
    return f"Next step: {recommendation_action}."

