from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.blending import DEFAULT_EVIDENCE_THRESHOLD, blended_topic_state
from app.core.diagnosis import diagnose_attempt
from app.core.next_step import recommend_next_step
from app.core.scoring import ScoringParams, default_state, expected_time_seconds, update_student_topic_state
from app.db import connect, init_db
from app.repo.edge_repo import get_prereq_topic_ids
from app.repo.question_repo import list_questions_by_topic
from app.repo.topic_repo import list_topics
from app.repo.population_repo import ensure_population_priors

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# -----------------------------
# Internal/admin demo metrics
# -----------------------------

# Student IDs used by the simulator (demo/test only).
# Important: the simulator oversamples weak topics for some profiles to make differences visible.
SIMULATED_STUDENT_IDS = {
    "stu_strong_overall",
    "stu_weak_in_fractions",
    "stu_good_but_slow",
    "stu_low_confidence",
    "stu_transfer_weak",
    "stu_hint_dependent",
    "stu_integer_strong",
    "stu_percent_struggles",
}
FRESH_STUDENT_ID = "stu_fresh"

# Mastery definition (demo thresholds; deterministic + explainable).
MASTERY_SCORE_MIN = 0.75
MASTERY_FRAGILITY_MAX = 0.30

# Fragile-success definition (correct, but at least one shaky signal).
FRAGILE_SLOW_RATIO_MIN = 1.4
FRAGILE_LOW_CONF_MAX = 2
FRAGILE_HINTS_MIN = 1
FRAGILE_ELEVATED_FRAGILITY_MIN = 0.60


@dataclass(frozen=True)
class _AttemptWithQuestion:
    attempt_id: str
    student_id: str
    question_id: str
    topic_id: str
    correctness: bool
    time_taken_seconds: int
    hints_used: int
    confidence_rating: int
    submitted_at: datetime
    # Question fields needed for scoring/diagnosis signals.
    question_text: str
    difficulty_prior: float
    conceptual_load: float
    procedural_load: float
    transfer_load: float
    diagnostic_value: float


def _parse_dt(s: str) -> datetime:
    # Stored as ISO-8601 text with 'Z' suffix. Keep tolerant for demo.
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _load_attempts_with_questions(conn) -> list[_AttemptWithQuestion]:
    rows = conn.execute(
        """
        SELECT
          a.id AS attempt_id,
          a.student_id,
          a.question_id,
          a.topic_id,
          a.correctness,
          a.time_taken_seconds,
          a.hints_used,
          a.confidence_rating,
          a.submitted_at,
          q.question_text,
          q.difficulty_prior,
          q.conceptual_load,
          q.procedural_load,
          q.transfer_load,
          q.diagnostic_value
        FROM attempts a
        LEFT JOIN questions q ON q.id = a.question_id
        ORDER BY a.student_id ASC, a.topic_id ASC, a.submitted_at ASC
        """
    ).fetchall()
    out: list[_AttemptWithQuestion] = []
    for r in rows:
        # In a healthy seed DB, questions always exist; keep safe defaults anyway.
        out.append(
            _AttemptWithQuestion(
                attempt_id=r["attempt_id"],
                student_id=r["student_id"],
                question_id=r["question_id"],
                topic_id=r["topic_id"],
                correctness=bool(r["correctness"]),
                time_taken_seconds=int(r["time_taken_seconds"]),
                hints_used=int(r["hints_used"]),
                confidence_rating=int(r["confidence_rating"]),
                submitted_at=_parse_dt(r["submitted_at"]),
                question_text=r["question_text"] or "",
                difficulty_prior=float(r["difficulty_prior"] or 0.5),
                conceptual_load=float(r["conceptual_load"] or 0.0),
                procedural_load=float(r["procedural_load"] or 0.0),
                transfer_load=float(r["transfer_load"] or 0.0),
                diagnostic_value=float(r["diagnostic_value"] or 0.0),
            )
        )
    return out


def _is_mastered(state) -> bool:
    return float(state.mastery_score) >= MASTERY_SCORE_MIN and float(state.fragility_score) <= MASTERY_FRAGILITY_MAX


def _is_fragile_success(a: _AttemptWithQuestion, state_after) -> bool:
    if not a.correctness:
        return False
    # Slow relative to expected time for that question.
    q_like = type(
        "Q",
        (),
        {
            "difficulty_prior": a.difficulty_prior,
            "conceptual_load": a.conceptual_load,
            "procedural_load": a.procedural_load,
            "transfer_load": a.transfer_load,
        },
    )()
    exp = expected_time_seconds(q_like, ScoringParams())
    slow = (a.time_taken_seconds / exp) >= FRAGILE_SLOW_RATIO_MIN if exp > 1e-6 else False
    hinty = a.hints_used >= FRAGILE_HINTS_MIN
    low_conf = a.confidence_rating <= FRAGILE_LOW_CONF_MAX
    elevated = float(state_after.fragility_score) >= FRAGILE_ELEVATED_FRAGILITY_MIN
    return bool(slow or hinty or low_conf or elevated)


def _compute_internal_metrics(conn) -> dict[str, Any]:
    """
    Lightweight admin-only metrics, computed from existing attempts + replayed topic-state updates.

    Important approximation:
    - We do not persist the recommendation shown at the time of an attempt.
      For demo/validation, we *recompute* the recommendation during replay using the current engine rules.
    """
    attempts = _load_attempts_with_questions(conn)
    total_attempts = len(attempts)
    total_students = len({a.student_id for a in attempts})

    # Data source distinction for auditability
    simulated_attempts = sum(1 for a in attempts if a.student_id in SIMULATED_STUDENT_IDS)
    fresh_manual_attempts = sum(1 for a in attempts if a.student_id == FRESH_STUDENT_ID)
    other_attempts = total_attempts - simulated_attempts - fresh_manual_attempts

    # Topic titles (for human-readable admin tables)
    topic_title_by_id = {t.id: t.title for t in list_topics(conn)}

    # Cache topic order and available questions by topic (needed for recommender).
    topics_in_order = [t.id for t in list_topics(conn)]
    questions_by_topic: dict[str, list] = {tid: list_questions_by_topic(conn, tid) for tid in topics_in_order}

    # Group attempts by (student, topic) for replay.
    by_st_topic: dict[tuple[str, str], list[_AttemptWithQuestion]] = {}
    for a in attempts:
        by_st_topic.setdefault((a.student_id, a.topic_id), []).append(a)

    # ---- 1) Time to mastery ----
    mastery_records_by_topic: dict[str, list[dict[str, Any]]] = {}

    # ---- 2) Fragility metrics ----
    fragile_correct_total = 0
    correct_total_by_topic: dict[str, int] = {}
    fragile_correct_by_topic: dict[str, int] = {}

    # ---- 3) Recommendation effectiveness (approx via replay) ----
    rec_used_by_action: dict[str, int] = {}
    rec_success_by_action: dict[str, int] = {}
    rec_action_source_counts = {"stored": 0, "recomputed": 0}
    low_data_threshold = 10  # used for subtle "low data" labels in UI

    # Stored recommendation map (when available)
    stored_recs = conn.execute(
        """
        SELECT attempt_id, recommendation_action
        FROM attempt_recommendations
        """
    ).fetchall()
    stored_action_by_attempt_id = {r["attempt_id"]: r["recommendation_action"] for r in stored_recs}

    for (student_id, topic_id), seq in by_st_topic.items():
        if not seq:
            continue

        # Replay personal topic state updates in chronological order.
        state = default_state(student_id, topic_id, now=seq[0].submitted_at)
        states_after: list = []
        for a in seq:
            # Minimal "question-like" object for scoring update (avoid importing full model here).
            q_like = type(
                "Q",
                (),
                {
                    "id": a.question_id,
                    "topic_id": topic_id,
                    "difficulty_prior": a.difficulty_prior,
                    "conceptual_load": a.conceptual_load,
                    "procedural_load": a.procedural_load,
                    "transfer_load": a.transfer_load,
                    "diagnostic_value": a.diagnostic_value,
                },
            )()
            # Minimal attempt-like object
            att_like = type(
                "A",
                (),
                {
                    "id": a.attempt_id,
                    "student_id": student_id,
                    "question_id": a.question_id,
                    "topic_id": topic_id,
                    "correctness": a.correctness,
                    "time_taken_seconds": a.time_taken_seconds,
                    "hints_used": a.hints_used,
                    "confidence_rating": a.confidence_rating,
                    "self_report_reason": None,
                    "submitted_at": a.submitted_at,
                },
            )()

            upd = update_student_topic_state(state, attempt=att_like, question=q_like)
            state = upd.new
            states_after.append(state)

            # Fragile success counts
            if a.correctness:
                correct_total_by_topic[topic_id] = correct_total_by_topic.get(topic_id, 0) + 1
            if _is_fragile_success(a, state):
                fragile_correct_total += 1
                fragile_correct_by_topic[topic_id] = fragile_correct_by_topic.get(topic_id, 0) + 1

        # Time to mastery: first time the replayed state hits mastery thresholds.
        mastered_idx = None
        for i, st_after in enumerate(states_after):
            if _is_mastered(st_after):
                mastered_idx = i
                break
        if mastered_idx is not None:
            t0 = seq[0].submitted_at
            tM = seq[mastered_idx].submitted_at
            rec = {
                "student_id": student_id,
                "attempts_to_mastery": mastered_idx + 1,
                "time_to_mastery_seconds": max(0, int((tM - t0).total_seconds())),
            }
            mastery_records_by_topic.setdefault(topic_id, []).append(rec)

        # Recommendation effectiveness (approx): recompute rec after each attempt and check next 1–2 attempts.
        # Use blended effective state for the recommender, matching the student engine behavior.
        pop_t = conn.execute(
            "SELECT calibrated_difficulty FROM population_topic_stats WHERE topic_id = ?",
            (topic_id,),
        ).fetchone()
        topic_cal = float(pop_t["calibrated_difficulty"]) if pop_t is not None else 0.5

        prereq_ids = get_prereq_topic_ids(conn, topic_id)
        available_qs = questions_by_topic.get(topic_id, [])

        for i in range(len(seq)):
            a = seq[i]
            st_after = states_after[i]
            effective_state, _, _ = blended_topic_state(
                st_after,
                population_calibrated_difficulty=topic_cal,
                threshold=DEFAULT_EVIDENCE_THRESHOLD,
            )

            # Diagnosis is recomputed without prereq states during replay (keeps it lightweight).
            q_like = type(
                "Q",
                (),
                {
                    "id": a.question_id,
                    "topic_id": topic_id,
                    "question_text": a.question_text,
                    "answer_type": "numeric",
                    "choices_json": "[]",
                    "correct_answer": "",
                    "secondary_topic_ids_json": "[]",
                    "difficulty_prior": a.difficulty_prior,
                    "conceptual_load": a.conceptual_load,
                    "procedural_load": a.procedural_load,
                    "transfer_load": a.transfer_load,
                    "diagnostic_value": a.diagnostic_value,
                    "hint_text": "",
                    "explanation_text": "",
                    "likely_error_tags_json": "[]",
                },
            )()
            att_like = type(
                "A",
                (),
                {
                    "id": a.attempt_id,
                    "student_id": student_id,
                    "question_id": a.question_id,
                    "topic_id": topic_id,
                    "correctness": a.correctness,
                    "time_taken_seconds": a.time_taken_seconds,
                    "hints_used": a.hints_used,
                    "confidence_rating": a.confidence_rating,
                    "self_report_reason": None,
                    "submitted_at": a.submitted_at,
                },
            )()
            dx = diagnose_attempt(attempt=att_like, question=q_like, topic_state=effective_state, prereq_states=[])

            latest_question = None
            # choose actual question object for recommender if available; otherwise keep dummy.
            for qq in available_qs:
                if getattr(qq, "id", None) == a.question_id:
                    latest_question = qq
                    break
            latest_question = latest_question or q_like

            # Use the stored recommendation action if present; otherwise recompute.
            action = stored_action_by_attempt_id.get(a.attempt_id)
            if action is not None:
                rec_action_source_counts["stored"] += 1
            else:
                rec = recommend_next_step(
                    latest_attempt=att_like,
                    latest_question=latest_question,
                    diagnosis_label=dx.label,
                    topic_state=effective_state,
                    prereq_topic_ids=prereq_ids,
                    topics_in_order=topics_in_order,
                    available_questions=available_qs,
                )
                action = rec.action
                rec_action_source_counts["recomputed"] += 1
            rec_used_by_action[action] = rec_used_by_action.get(action, 0) + 1

            # Look ahead next 1–2 attempts for improvements.
            base = seq[i]
            base_state = states_after[i]
            success = False
            for j in range(i + 1, min(i + 3, len(seq))):
                nxt = seq[j]
                nxt_state = states_after[j]

                improved_correctness = (not base.correctness) and nxt.correctness
                improved_time = nxt.time_taken_seconds < int(base.time_taken_seconds * 0.85) if base.time_taken_seconds > 0 else False
                improved_hints = nxt.hints_used < base.hints_used
                improved_mastery = (float(nxt_state.mastery_score) - float(base_state.mastery_score)) >= 0.05
                improved_fragility = (float(base_state.fragility_score) - float(nxt_state.fragility_score)) >= 0.05

                if improved_correctness or improved_time or improved_hints or improved_mastery or improved_fragility:
                    success = True
                    break

            if success:
                rec_success_by_action[action] = rec_success_by_action.get(action, 0) + 1

    # Build mastery aggregates per topic
    mastery_by_topic = []
    for topic_id, recs in mastery_records_by_topic.items():
        if not recs:
            continue
        avg_attempts = sum(r["attempts_to_mastery"] for r in recs) / float(len(recs))
        avg_time_s = sum(r["time_to_mastery_seconds"] for r in recs) / float(len(recs))
        mastery_by_topic.append(
            {
                "topic_id": topic_id,
                "topic_title": topic_title_by_id.get(topic_id) or topic_id,
                "students_mastered": len(recs),
                "avg_attempts_to_mastery": avg_attempts,
                "avg_time_to_mastery_seconds": avg_time_s,
            }
        )
    mastery_by_topic.sort(key=lambda x: (x["avg_attempts_to_mastery"], x["avg_time_to_mastery_seconds"]))

    fastest_mastery = mastery_by_topic[:5]
    slowest_mastery = list(reversed(mastery_by_topic[-5:])) if mastery_by_topic else []

    # Fragility by topic (rate among correct attempts)
    fragility_by_topic = []
    for topic_id, correct_n in correct_total_by_topic.items():
        frag_n = fragile_correct_by_topic.get(topic_id, 0)
        rate = (frag_n / float(correct_n)) if correct_n > 0 else 0.0
        fragility_by_topic.append(
            {
                "topic_id": topic_id,
                "correct_attempts": correct_n,
                "fragile_correct_attempts": frag_n,
                "fragile_success_rate": rate,
            }
        )
    fragility_by_topic.sort(key=lambda x: x["fragile_success_rate"], reverse=True)
    highest_fragility_topics = fragility_by_topic[:8]

    # Recommendation effectiveness table
    rec_rows = []
    for action, used in sorted(rec_used_by_action.items(), key=lambda kv: (-kv[1], kv[0])):
        succ = rec_success_by_action.get(action, 0)
        rate = (succ / float(used)) if used > 0 else 0.0
        rec_rows.append(
            {
                "action": action,
                "used": used,
                "success": succ,
                "improvement_rate": rate,
            }
        )

    rec_used_total = sum(rec_used_by_action.values())
    rec_success_total = sum(rec_success_by_action.values())
    rec_overall_rate = (rec_success_total / float(rec_used_total)) if rec_used_total > 0 else None

    # Best/weakest recommendation types (simple: among used>0)
    best_rec = None
    weakest_rec = None
    if rec_rows:
        best_rec = max(rec_rows, key=lambda r: (r["improvement_rate"], r["used"]))
        weakest_rec = min(rec_rows, key=lambda r: (r["improvement_rate"], -r["used"]))

    topics_reaching_mastery = sum(1 for r in mastery_by_topic if r["students_mastered"] > 0)

    return {
        "summary": {
            "total_attempts": total_attempts,
            "total_students": total_students,
            "topics_reaching_mastery": topics_reaching_mastery,
            "fragile_success_count": fragile_correct_total,
            "recommendation_overall_used": rec_used_total,
            "recommendation_overall_improvement_rate": rec_overall_rate,
            "data_sources": {
                "simulated_attempts": simulated_attempts,
                "fresh_manual_attempts": fresh_manual_attempts,
                "other_attempts": other_attempts,
            },
        },
        "time_to_mastery": {
            "definition": {
                "mastery_score_min": MASTERY_SCORE_MIN,
                "fragility_score_max": MASTERY_FRAGILITY_MAX,
            },
            "by_topic": mastery_by_topic,
            "fastest_topics": fastest_mastery,
            "slowest_topics": slowest_mastery,
        },
        "fragility_metrics": {
            "definition": {
                "fragile_slow_ratio_min": FRAGILE_SLOW_RATIO_MIN,
                "fragile_low_conf_max": FRAGILE_LOW_CONF_MAX,
                "fragile_hints_min": FRAGILE_HINTS_MIN,
                "fragile_elevated_fragility_min": FRAGILE_ELEVATED_FRAGILITY_MIN,
            },
            "fragile_correct_total": fragile_correct_total,
            "by_topic": fragility_by_topic,
            "highest_fragility_topics": highest_fragility_topics,
        },
        "recommendation_effectiveness": {
            "approximation_note": (
                "Recommendation effectiveness uses the next 1–2 attempts on the same topic for the same student. "
                "If the actual recommendation was stored at attempt time, we use it; otherwise we recompute it during replay."
            ),
            "overall_improvement_rate": rec_overall_rate,
            "best": best_rec,
            "weakest": weakest_rec,
            "rows": rec_rows,
            "action_source_counts": rec_action_source_counts,
        },
        "audit_notes": {
            "simulated_students": sorted(SIMULATED_STUDENT_IDS),
            "simulation_note": (
                "Demo simulations intentionally oversample weak topics for some profiles "
                "and focus practice for the strong-overall profile to make dashboard differences visible."
            ),
            "low_data_threshold": low_data_threshold,
        },
    }


@router.get("/internal/analytics", response_class=HTMLResponse)
def internal_analytics(request: Request) -> HTMLResponse:
    """
    Internal/admin-only demo view for inspecting population calibration.
    Not linked from student-facing navigation.
    """
    conn = connect()
    try:
        init_db(conn)
        ensure_population_priors(conn)

        metrics = _compute_internal_metrics(conn)

        topic_rows = conn.execute(
            """
            SELECT
              pts.topic_id,
              t.title AS topic_title,
              pts.attempt_count,
              pts.avg_correctness,
              pts.avg_hints_used,
              pts.avg_time_taken_seconds,
              pts.prior_difficulty,
              pts.calibrated_difficulty,
              pts.updated_at
            FROM population_topic_stats pts
            LEFT JOIN topics t ON t.id = pts.topic_id
            ORDER BY pts.calibrated_difficulty DESC, pts.attempt_count DESC
            """
        ).fetchall()

        question_rows = conn.execute(
            """
            SELECT
              pqs.question_id,
              q.topic_id,
              substr(q.question_text, 1, 120) AS question_text_short,
              pqs.attempt_count,
              pqs.avg_correctness,
              pqs.avg_hints_used,
              pqs.avg_time_taken_seconds,
              pqs.prior_difficulty,
              pqs.calibrated_difficulty,
              pqs.updated_at
            FROM population_question_stats pqs
            LEFT JOIN questions q ON q.id = pqs.question_id
            ORDER BY pqs.calibrated_difficulty DESC, pqs.attempt_count DESC
            LIMIT 80
            """
        ).fetchall()

        def _to_dict(r) -> dict[str, Any]:
            return {k: r[k] for k in r.keys()}

        return templates.TemplateResponse(
            "internal_analytics.html",
            {
                "request": request,
                "title": "Internal analytics (admin only)",
                "metrics": metrics,
                "topic_stats": [_to_dict(r) for r in topic_rows],
                "question_stats": [_to_dict(r) for r in question_rows],
            },
        )
    finally:
        conn.close()

