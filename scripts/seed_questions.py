from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import connect, init_db  # noqa: E402


SEED_PATH = Path("data/grade7_math_questions_seed_12topics.json")


def seed_questions(seed_path: Path = SEED_PATH) -> None:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    conn = connect()
    init_db(conn)

    with conn:
        for q in questions:
            conn.execute(
                """
                INSERT OR REPLACE INTO questions
                (id, topic_id, secondary_topic_ids_json, question_text, answer_type, choices_json, correct_answer,
                 difficulty_prior, conceptual_load, procedural_load, transfer_load, diagnostic_value,
                 hint_text, explanation_text, likely_error_tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    q["id"],
                    q["topic_id"],
                    json.dumps(q.get("secondary_topic_ids", [])),
                    q["question_text"],
                    q["answer_type"],
                    json.dumps(q.get("choices", [])),
                    str(q["correct_answer"]),
                    float(q["difficulty_prior"]),
                    float(q["conceptual_load"]),
                    float(q["procedural_load"]),
                    float(q["transfer_load"]),
                    float(q["diagnostic_value"]),
                    q.get("hint_text", ""),
                    q.get("explanation_text", ""),
                    json.dumps(q.get("likely_error_tags", [])),
                ),
            )


def main() -> None:
    seed_questions()
    print(f"OK: seeded questions from {SEED_PATH}")


if __name__ == "__main__":
    main()

