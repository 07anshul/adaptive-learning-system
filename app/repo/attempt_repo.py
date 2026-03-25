from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.models.domain import Attempt


def _dt_to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_to_dt(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def insert_attempt(conn: sqlite3.Connection, attempt: Attempt) -> None:
    conn.execute(
        """
        INSERT INTO attempts
        (id, student_id, question_id, topic_id, correctness, time_taken_seconds, hints_used,
         confidence_rating, self_report_reason, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attempt.id,
            attempt.student_id,
            attempt.question_id,
            attempt.topic_id,
            1 if attempt.correctness else 0,
            int(attempt.time_taken_seconds),
            int(attempt.hints_used),
            int(attempt.confidence_rating),
            attempt.self_report_reason,
            _dt_to_iso(attempt.submitted_at),
        ),
    )


def list_recent_attempts(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    limit: int = 20,
) -> list[Attempt]:
    rows = conn.execute(
        """
        SELECT id, student_id, question_id, topic_id, correctness, time_taken_seconds, hints_used,
               confidence_rating, self_report_reason, submitted_at
        FROM attempts
        WHERE student_id = ?
        ORDER BY submitted_at DESC
        LIMIT ?
        """,
        (student_id, int(limit)),
    ).fetchall()
    return [_row_to_attempt(r) for r in rows]


def list_recent_attempts_for_topic(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    topic_id: str,
    limit: int = 20,
) -> list[Attempt]:
    rows = conn.execute(
        """
        SELECT id, student_id, question_id, topic_id, correctness, time_taken_seconds, hints_used,
               confidence_rating, self_report_reason, submitted_at
        FROM attempts
        WHERE student_id = ? AND topic_id = ?
        ORDER BY submitted_at DESC
        LIMIT ?
        """,
        (student_id, topic_id, int(limit)),
    ).fetchall()
    return [_row_to_attempt(r) for r in rows]


def _row_to_attempt(r: sqlite3.Row) -> Attempt:
    return Attempt(
        id=r["id"],
        student_id=r["student_id"],
        question_id=r["question_id"],
        topic_id=r["topic_id"],
        correctness=bool(r["correctness"]),
        time_taken_seconds=int(r["time_taken_seconds"]),
        hints_used=int(r["hints_used"]),
        confidence_rating=int(r["confidence_rating"]),
        self_report_reason=r["self_report_reason"],
        submitted_at=_iso_to_dt(r["submitted_at"]),
    )

