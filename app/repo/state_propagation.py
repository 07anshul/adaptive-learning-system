from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import sqlite3

from app.core.scoring import clamp01
from app.models.domain import StudentTopicState
from app.repo.student_state_repo import get_student_topic_state, upsert_student_topic_state


def apply_soft_neighbor_update(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    topic_id: str,
    mastery_delta: float,
    fragility_delta: float,
    fluency_delta: float,
    weight: float,
    scale: float = 0.12,
) -> None:
    """
    Conservative propagation for demo:
    - does NOT increment evidence_count
    - small scaled adjustments only
    """
    st = get_student_topic_state(conn, student_id=student_id, topic_id=topic_id)
    if st is None:
        # If missing, skip (fresh student has rows anyway; keep simple).
        return
    s = scale * max(0.0, min(1.0, float(weight)))
    new = StudentTopicState(
        student_id=st.student_id,
        topic_id=st.topic_id,
        mastery_score=clamp01(st.mastery_score + s * mastery_delta),
        fragility_score=clamp01(st.fragility_score + s * fragility_delta),
        fluency_score=clamp01(st.fluency_score + s * fluency_delta),
        evidence_count=st.evidence_count,
        last_updated_at=datetime.now(tz=timezone.utc),
    )
    upsert_student_topic_state(conn, new)

