from __future__ import annotations

import json
import sqlite3
from typing import Optional

from app.models.domain import Question


def list_questions_by_topic(conn: sqlite3.Connection, topic_id: str) -> list[Question]:
    rows = conn.execute(
        """
        SELECT id, prompt, question_type, choices_json, correct_answer,
               primary_topic_id, secondary_topic_ids_json,
               difficulty_prior, conceptual_load, procedural_load, transfer_load, diagnostic_value,
               tags_json
        FROM questions
        WHERE primary_topic_id = ?
        ORDER BY id ASC
        """,
        (topic_id,),
    ).fetchall()
    return [_row_to_question(r) for r in rows]


def get_question(conn: sqlite3.Connection, question_id: str) -> Optional[Question]:
    r = conn.execute(
        """
        SELECT id, prompt, question_type, choices_json, correct_answer,
               primary_topic_id, secondary_topic_ids_json,
               difficulty_prior, conceptual_load, procedural_load, transfer_load, diagnostic_value,
               tags_json
        FROM questions
        WHERE id = ?
        """,
        (question_id,),
    ).fetchone()
    if r is None:
        return None
    return _row_to_question(r)


def _row_to_question(r: sqlite3.Row) -> Question:
    return Question(
        id=r["id"],
        prompt=r["prompt"],
        question_type=r["question_type"],
        choices=json.loads(r["choices_json"] or "[]"),
        correct_answer=r["correct_answer"],
        primary_topic_id=r["primary_topic_id"],
        secondary_topic_ids=json.loads(r["secondary_topic_ids_json"] or "[]"),
        difficulty_prior=float(r["difficulty_prior"]),
        conceptual_load=float(r["conceptual_load"]),
        procedural_load=float(r["procedural_load"]),
        transfer_load=float(r["transfer_load"]),
        diagnostic_value=float(r["diagnostic_value"]),
        tags=json.loads(r["tags_json"] or "[]"),
    )

