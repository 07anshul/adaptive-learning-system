from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from app.models.domain import StudentTopicState


def _dt_to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_to_dt(s: str) -> datetime:
    # Minimal ISO parser for our own emitted "Z" timestamps.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def get_student_topic_state(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    topic_id: str,
) -> Optional[StudentTopicState]:
    row = conn.execute(
        """
        SELECT student_id, topic_id, mastery_score, fragility_score, fluency_score, evidence_count, last_updated_at
        FROM student_topic_state
        WHERE student_id = ? AND topic_id = ?
        """,
        (student_id, topic_id),
    ).fetchone()
    if row is None:
        return None
    return StudentTopicState(
        student_id=row["student_id"],
        topic_id=row["topic_id"],
        mastery_score=float(row["mastery_score"]),
        fragility_score=float(row["fragility_score"]),
        fluency_score=float(row["fluency_score"]),
        evidence_count=int(row["evidence_count"]),
        last_updated_at=_iso_to_dt(row["last_updated_at"]),
    )


def upsert_student_topic_state(conn: sqlite3.Connection, state: StudentTopicState) -> None:
    conn.execute(
        """
        INSERT INTO student_topic_state
        (student_id, topic_id, mastery_score, fragility_score, fluency_score, evidence_count, last_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id, topic_id) DO UPDATE SET
          mastery_score = excluded.mastery_score,
          fragility_score = excluded.fragility_score,
          fluency_score = excluded.fluency_score,
          evidence_count = excluded.evidence_count,
          last_updated_at = excluded.last_updated_at
        """,
        (
            state.student_id,
            state.topic_id,
            float(state.mastery_score),
            float(state.fragility_score),
            float(state.fluency_score),
            int(state.evidence_count),
            _dt_to_iso(state.last_updated_at),
        ),
    )

