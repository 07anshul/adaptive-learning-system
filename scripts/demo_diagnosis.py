from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.diagnosis import diagnose_attempt  # noqa: E402
from app.models.domain import Attempt, Question, StudentTopicState  # noqa: E402


def main() -> None:
    now = datetime.now(tz=timezone.utc)
    student_id = "stu_demo"
    topic_id = "t_percent_of_quantity"

    # Topic state: okay-ish mastery but fragile/slow.
    topic_state = StudentTopicState(
        student_id=student_id,
        topic_id=topic_id,
        mastery_score=0.58,
        fragility_score=0.62,
        fluency_score=0.40,
        evidence_count=12,
        last_updated_at=now,
    )

    prereq_states = [
        StudentTopicState(
            student_id=student_id,
            topic_id="t_percent_convert",
            mastery_score=0.30,  # substantially weaker prerequisite
            fragility_score=0.70,
            fluency_score=0.28,
            evidence_count=10,
            last_updated_at=now,
        )
    ]

    # Question: high transfer/word problem style
    q = Question(
        id="q_transfer_001",
        prompt="A jacket costs $80. It is discounted by 25%. What is the sale price?",
        question_type="short",
        choices=[],
        correct_answer="60",
        primary_topic_id=topic_id,
        secondary_topic_ids=[],
        difficulty_prior=0.60,
        conceptual_load=0.55,
        procedural_load=0.45,
        transfer_load=0.75,
        diagnostic_value=0.70,
        tags=["word_problem"],
    )

    att_wrong = Attempt(
        id="att_001",
        student_id=student_id,
        question_id=q.id,
        topic_id=topic_id,
        correctness=False,
        time_taken_seconds=85,
        hints_used=1,
        confidence_rating=2,
        self_report_reason="I wasn't sure whether to multiply or subtract first.",
        submitted_at=now,
    )

    d1 = diagnose_attempt(
        attempt=att_wrong,
        question=q,
        topic_state=topic_state,
        prereq_states=prereq_states,
    )
    print("\nCASE 1 (wrong + weak prereq):", d1.label, "-", d1.summary)
    print("evidence:", d1.evidence)

    # CASE 2: correct but slow/low-confidence/hints => fragile_understanding
    att_fragile = Attempt(
        id="att_002",
        student_id=student_id,
        question_id=q.id,
        topic_id=topic_id,
        correctness=True,
        time_taken_seconds=95,
        hints_used=1,
        confidence_rating=2,
        self_report_reason=None,
        submitted_at=now,
    )
    d2 = diagnose_attempt(
        attempt=att_fragile,
        question=q,
        topic_state=topic_state,
        prereq_states=[],  # show it works without graph edges
    )
    print("\nCASE 2 (correct but shaky):", d2.label, "-", d2.summary)
    print("evidence:", d2.evidence)


if __name__ == "__main__":
    main()

