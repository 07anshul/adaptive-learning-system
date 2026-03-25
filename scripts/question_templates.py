"""
Scriptable patterns/templates for generating the remaining demo questions consistently.

Goal: keep it simple. You can hand-edit or programmatically expand these templates into
`data/grade7_math_questions_seed_all.json` later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional


AnswerType = Literal["numeric", "mcq", "short_text"]


@dataclass(frozen=True)
class QuestionTemplate:
    topic_id: str
    base_id: str  # e.g. "q_t_integer_add_sub"
    answer_type: AnswerType
    question_text: str
    correct_answer: str
    choices: Optional[List[str]] = None
    secondary_topic_ids: Optional[List[str]] = None

    # Difficulty + cognitive dimensions (0..1)
    difficulty_prior: float = 0.50
    conceptual_load: float = 0.40
    procedural_load: float = 0.40
    transfer_load: float = 0.10
    diagnostic_value: float = 0.50

    hint_text: str = ""
    explanation_text: str = ""
    likely_error_tags: Optional[List[str]] = None

    def materialize(self, n: int) -> Dict[str, Any]:
        """
        Deterministic ID convention:
          id = f"{base_id}_{n:03d}"
        """
        return {
            "id": f"{self.base_id}_{n:03d}",
            "topic_id": self.topic_id,
            "secondary_topic_ids": self.secondary_topic_ids or [],
            "question_text": self.question_text,
            "answer_type": self.answer_type,
            "choices": self.choices or [],
            "correct_answer": self.correct_answer,
            "difficulty_prior": self.difficulty_prior,
            "conceptual_load": self.conceptual_load,
            "procedural_load": self.procedural_load,
            "transfer_load": self.transfer_load,
            "diagnostic_value": self.diagnostic_value,
            "hint_text": self.hint_text,
            "explanation_text": self.explanation_text,
            "likely_error_tags": self.likely_error_tags or [],
        }


def suggested_patterns_for_topic(topic_id: str) -> List[str]:
    """
    Lightweight template guidance (so you can scale quickly to ~150 items):

    - 2x direct computation (easy/medium)
    - 1x diagnostic misconception trap (high diagnostic_value)
    - 1x word problem (higher transfer_load)
    - optional 1x mixed/reflective item ("explain your step" as short_text)
    """
    return [
        f"{topic_id}: direct_easy",
        f"{topic_id}: direct_medium",
        f"{topic_id}: diagnostic_trap",
        f"{topic_id}: word_problem_transfer",
        f"{topic_id}: optional_explain_step",
    ]

