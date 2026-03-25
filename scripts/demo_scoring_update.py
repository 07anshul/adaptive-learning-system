from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.scoring import update_student_topic_state  # noqa: E402
from app.db import connect, init_db  # noqa: E402
from app.models.domain import Attempt, Question  # noqa: E402
from app.repo.student_state_repo import (  # noqa: E402
    get_student_topic_state,
    upsert_student_topic_state,
)


def main() -> None:
    conn = connect()
    init_db(conn)

    student_id = "stu_demo"
    topic_id = "t_integer_add_sub"

    # Ensure FK rows exist (demo-only convenience).
    with conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO students (id, display_name, created_at)
            VALUES (?, ?, ?)
            """,
            (student_id, "Demo Student", now := datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO topics
            (id, title, description, cluster, grade_level, order_index, difficulty_prior, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, '[]')
            """,
            (
                topic_id,
                "Add & subtract integers",
                "Compute sums/differences with negatives; interpret with contexts.",
                "Integers",
                7,
                4,
                0.40,
            ),
        )

    # A minimal question object for scoring demo (normally fetched from DB)
    q = Question(
        id="q_demo_001",
        topic_id=topic_id,
        secondary_topic_ids=[],
        question_text="Compute: -7 + 12",
        answer_type="mcq",
        choices=["-19", "-5", "5", "19"],
        correct_answer="5",
        difficulty_prior=0.35,
        conceptual_load=0.30,
        procedural_load=0.40,
        transfer_load=0.10,
        diagnostic_value=0.55,
        hint_text="Think: 12 − 7.",
        explanation_text="-7 + 12 = 5",
        likely_error_tags=["sign_error"],
    )

    prev = get_student_topic_state(conn, student_id=student_id, topic_id=topic_id)
    print("BEFORE:", prev.model_dump() if prev else None)

    now = datetime.now(tz=timezone.utc)
    attempts = [
        Attempt(
            id="att_demo_001",
            student_id=student_id,
            question_id=q.id,
            topic_id=topic_id,
            correctness=True,
            time_taken_seconds=18,
            hints_used=0,
            confidence_rating=5,
            self_report_reason=None,
            submitted_at=now,
        ),
        Attempt(
            id="att_demo_002",
            student_id=student_id,
            question_id=q.id,
            topic_id=topic_id,
            correctness=True,
            time_taken_seconds=75,
            hints_used=1,
            confidence_rating=2,
            self_report_reason="I guessed after a hint.",
            submitted_at=now,
        ),
        Attempt(
            id="att_demo_003",
            student_id=student_id,
            question_id=q.id,
            topic_id=topic_id,
            correctness=False,
            time_taken_seconds=60,
            hints_used=2,
            confidence_rating=2,
            self_report_reason="I kept mixing up the signs.",
            submitted_at=now,
        ),
    ]

    state = prev
    for i, att in enumerate(attempts, start=1):
        upd = update_student_topic_state(state, attempt=att, question=q)
        state = upd.new
        upsert_student_topic_state(conn, state)
        conn.commit()
        print(f"\nATTEMPT {i}: features={upd.features}")
        print("DELTA:", {"mastery": upd.mastery_delta, "fluency": upd.fluency_delta, "fragility": upd.fragility_delta})
        print("AFTER:", state.model_dump())


if __name__ == "__main__":
    main()

