from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.core.population import (
    calibrated_difficulty,
    observed_difficulty_from_aggregates,
)
from app.core.scoring import ScoringParams, expected_time_seconds
from app.models.domain import Attempt, Question


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_population_priors(conn: sqlite3.Connection) -> None:
    """
    Idempotent: ensures every topic/question has a population row with:
      calibrated == prior, attempt_count == 0
    """
    now = _iso(datetime.now(tz=timezone.utc))

    # Topics
    topics = conn.execute("SELECT id, difficulty_prior FROM topics").fetchall()
    for r in topics:
        conn.execute(
            """
            INSERT OR IGNORE INTO population_topic_stats
            (topic_id, prior_difficulty, calibrated_difficulty, attempt_count, avg_correctness, avg_hints_used, avg_time_taken_seconds, updated_at)
            VALUES (?, ?, ?, 0, 0.0, 0.0, 0.0, ?)
            """,
            (r["id"], float(r["difficulty_prior"]), float(r["difficulty_prior"]), now),
        )

    # Questions
    qs = conn.execute("SELECT id, difficulty_prior FROM questions").fetchall()
    for r in qs:
        conn.execute(
            """
            INSERT OR IGNORE INTO population_question_stats
            (question_id, prior_difficulty, calibrated_difficulty, attempt_count, avg_correctness, avg_hints_used, avg_time_taken_seconds, updated_at)
            VALUES (?, ?, ?, 0, 0.0, 0.0, 0.0, ?)
            """,
            (r["id"], float(r["difficulty_prior"]), float(r["difficulty_prior"]), now),
        )


def get_population_question_difficulty(conn: sqlite3.Connection, question_id: str) -> Optional[Tuple[float, float]]:
    r = conn.execute(
        """
        SELECT prior_difficulty, calibrated_difficulty
        FROM population_question_stats
        WHERE question_id = ?
        """,
        (question_id,),
    ).fetchone()
    if r is None:
        return None
    return float(r["prior_difficulty"]), float(r["calibrated_difficulty"])


def get_population_topic_difficulty(conn: sqlite3.Connection, topic_id: str) -> Optional[Tuple[float, float]]:
    r = conn.execute(
        """
        SELECT prior_difficulty, calibrated_difficulty
        FROM population_topic_stats
        WHERE topic_id = ?
        """,
        (topic_id,),
    ).fetchone()
    if r is None:
        return None
    return float(r["prior_difficulty"]), float(r["calibrated_difficulty"])


def update_population_from_attempt(
    conn: sqlite3.Connection,
    *,
    attempt: Attempt,
    question: Question,
    now: Optional[datetime] = None,
) -> None:
    """
    Updates population aggregates for:
    - question difficulty estimate
    - topic difficulty estimate
    - avg hints, avg time, avg correctness

    Deterministic, interpretable, no-ML.
    """
    ensure_population_priors(conn)
    ts = _iso(now or attempt.submitted_at)

    # --- Question aggregates ---
    qr = conn.execute(
        """
        SELECT prior_difficulty, calibrated_difficulty, attempt_count, avg_correctness, avg_hints_used, avg_time_taken_seconds
        FROM population_question_stats
        WHERE question_id = ?
        """,
        (question.id,),
    ).fetchone()

    if qr is None:
        return

    q_n = int(qr["attempt_count"])
    q_avg_corr = float(qr["avg_correctness"])
    q_avg_hints = float(qr["avg_hints_used"])
    q_avg_time = float(qr["avg_time_taken_seconds"])
    q_prior = float(qr["prior_difficulty"])

    x_corr = 1.0 if attempt.correctness else 0.0
    x_hints = float(attempt.hints_used)
    x_time = float(attempt.time_taken_seconds)

    q_new_avg_corr = (q_avg_corr * q_n + x_corr) / float(q_n + 1)
    q_new_avg_hints = (q_avg_hints * q_n + x_hints) / float(q_n + 1)
    q_new_avg_time = (q_avg_time * q_n + x_time) / float(q_n + 1)

    exp_time = expected_time_seconds(question, ScoringParams())
    q_observed = observed_difficulty_from_aggregates(
        avg_correctness=q_new_avg_corr,
        avg_hints_used=q_new_avg_hints,
        avg_time_taken_seconds=q_new_avg_time,
        expected_time_s=exp_time,
    )
    q_cal = calibrated_difficulty(prior=q_prior, observed=q_observed, prior_weight=0.60)

    conn.execute(
        """
        UPDATE population_question_stats
        SET attempt_count = ?,
            avg_correctness = ?,
            avg_hints_used = ?,
            avg_time_taken_seconds = ?,
            calibrated_difficulty = ?,
            updated_at = ?
        WHERE question_id = ?
        """,
        (q_n + 1, q_new_avg_corr, q_new_avg_hints, q_new_avg_time, q_cal, ts, question.id),
    )

    # --- Topic aggregates ---
    tr = conn.execute(
        """
        SELECT prior_difficulty, calibrated_difficulty, attempt_count, avg_correctness, avg_hints_used, avg_time_taken_seconds
        FROM population_topic_stats
        WHERE topic_id = ?
        """,
        (question.topic_id,),
    ).fetchone()
    if tr is None:
        return

    t_n = int(tr["attempt_count"])
    t_avg_corr = float(tr["avg_correctness"])
    t_avg_hints = float(tr["avg_hints_used"])
    t_avg_time = float(tr["avg_time_taken_seconds"])
    t_prior = float(tr["prior_difficulty"])

    t_new_avg_corr = (t_avg_corr * t_n + x_corr) / float(t_n + 1)
    t_new_avg_hints = (t_avg_hints * t_n + x_hints) / float(t_n + 1)
    t_new_avg_time = (t_avg_time * t_n + x_time) / float(t_n + 1)

    # Topic expected time: use the question's expected time as a proxy (simple demo).
    t_observed = observed_difficulty_from_aggregates(
        avg_correctness=t_new_avg_corr,
        avg_hints_used=t_new_avg_hints,
        avg_time_taken_seconds=t_new_avg_time,
        expected_time_s=exp_time,
    )
    t_cal = calibrated_difficulty(prior=t_prior, observed=t_observed, prior_weight=0.60)

    conn.execute(
        """
        UPDATE population_topic_stats
        SET attempt_count = ?,
            avg_correctness = ?,
            avg_hints_used = ?,
            avg_time_taken_seconds = ?,
            calibrated_difficulty = ?,
            updated_at = ?
        WHERE topic_id = ?
        """,
        (t_n + 1, t_new_avg_corr, t_new_avg_hints, t_new_avg_time, t_cal, ts, question.topic_id),
    )

