from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.core.diagnosis import diagnose_attempt
from app.core.next_step import recommend_next_step
from app.core.scoring import default_state, update_student_topic_state
from app.core.explanations import explain_diagnosis, explain_recommendation
from app.core.blending import blended_topic_state, DEFAULT_EVIDENCE_THRESHOLD
from app.db import connect, init_db
from app.models.domain import Attempt, Question, StudentTopicState
from app.ui import router as ui_router
from app.repo.attempt_repo import (
    insert_attempt,
    list_recent_attempts,
    list_recent_attempts_for_topic,
)
from app.repo.edge_repo import get_prereq_topic_ids, list_edges_for_topic
from app.repo.edge_repo import get_encompassing_parent_ids, get_edge_weight
from app.repo.question_repo import get_question, list_questions_by_topic
from app.repo.student_state_repo import get_student_topic_state, upsert_student_topic_state
from app.repo.topic_repo import get_topic, list_topics
from app.repo.population_repo import (
    update_population_from_attempt,
    ensure_population_priors,
    get_population_question_difficulty,
    get_population_topic_difficulty,
)
from app.repo.state_propagation import apply_soft_neighbor_update


app = FastAPI(title="Adaptive Learning System (Demo API)")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(ui_router)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_student_exists(conn, student_id: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO students (id, display_name, created_at)
        VALUES (?, ?, ?)
        """,
        (student_id, f"Student {student_id}", _iso(_now())),
    )


class AttemptCreateRequest(BaseModel):
    student_id: str
    question_id: str
    topic_id: Optional[str] = None

    correctness: bool
    time_taken_seconds: int = Field(ge=0)
    hints_used: int = Field(ge=0)
    confidence_rating: int = Field(ge=1, le=5)
    self_report_reason: Optional[str] = None


class AttemptCreateResponse(BaseModel):
    attempt: dict[str, Any]
    topic_state: dict[str, Any]
    diagnosis: dict[str, Any]
    recommendation: dict[str, Any]


class DashboardResponse(BaseModel):
    strongest_topics: list[dict[str, Any]]
    weakest_topics: list[dict[str, Any]]
    fragile_topics: list[dict[str, Any]]
    recent_attempts: list[dict[str, Any]]
    next_recommended_action: dict[str, Any]


@app.on_event("startup")
def _startup() -> None:
    conn = connect()
    init_db(conn)
    conn.close()


@app.get("/topics")
def get_topics() -> list[dict[str, Any]]:
    conn = connect()
    try:
        topics = list_topics(conn)
        return [t.model_dump() for t in topics]
    finally:
        conn.close()


@app.get("/topics/{topic_id}")
def get_topic_by_id(topic_id: str) -> dict[str, Any]:
    conn = connect()
    try:
        t = get_topic(conn, topic_id)
        if t is None:
            raise HTTPException(status_code=404, detail="topic_not_found")
        edges = list_edges_for_topic(conn, topic_id)
        return {"topic": t.model_dump(), "edges": edges}
    finally:
        conn.close()


@app.get("/questions")
def get_questions(topicId: str = Query(...)) -> list[dict[str, Any]]:
    conn = connect()
    try:
        qs = list_questions_by_topic(conn, topicId)
        return [q.model_dump() for q in qs]
    finally:
        conn.close()


@app.post("/attempts")
def post_attempt(req: AttemptCreateRequest) -> AttemptCreateResponse:
    conn = connect()
    try:
        init_db(conn)
        _ensure_student_exists(conn, req.student_id)
        ensure_population_priors(conn)

        q = get_question(conn, req.question_id)
        if q is None:
            raise HTTPException(status_code=404, detail="question_not_found")

        topic_id = req.topic_id or q.topic_id

        # Use population-calibrated difficulty as the active prior (separate from student state).
        pop_q = get_population_question_difficulty(conn, q.id)
        if pop_q is not None:
            q = q.model_copy(update={"difficulty_prior": pop_q[1]})

        # Save attempt
        att = Attempt(
            id=f"att_{uuid.uuid4().hex[:12]}",
            student_id=req.student_id,
            question_id=req.question_id,
            topic_id=topic_id,
            correctness=req.correctness,
            time_taken_seconds=req.time_taken_seconds,
            hints_used=req.hints_used,
            confidence_rating=req.confidence_rating,
            self_report_reason=req.self_report_reason,
            submitted_at=_now(),
        )
        with conn:
            insert_attempt(conn, att)

        # Update topic state
        prev_state = get_student_topic_state(conn, student_id=req.student_id, topic_id=topic_id)
        upd = update_student_topic_state(prev_state, attempt=att, question=q)
        with conn:
            upsert_student_topic_state(conn, upd.new)

        # Update global population calibration (separate from student state)
        with conn:
            update_population_from_attempt(conn, attempt=att, question=q)

        # Optional conservative neighbor-topic propagation (only if edges exist)
        with conn:
            prereqs = get_prereq_topic_ids(conn, topic_id)
            for pid in prereqs:
                w = get_edge_weight(conn, pid, topic_id, "prerequisite")
                apply_soft_neighbor_update(
                    conn,
                    student_id=req.student_id,
                    topic_id=pid,
                    mastery_delta=upd.mastery_delta,
                    fragility_delta=upd.fragility_delta,
                    fluency_delta=upd.fluency_delta,
                    weight=w,
                    scale=0.08,
                )
            parents = get_encompassing_parent_ids(conn, topic_id)
            for parent_id in parents:
                w = get_edge_weight(conn, parent_id, topic_id, "encompassing")
                apply_soft_neighbor_update(
                    conn,
                    student_id=req.student_id,
                    topic_id=parent_id,
                    mastery_delta=upd.mastery_delta,
                    fragility_delta=upd.fragility_delta,
                    fluency_delta=upd.fluency_delta,
                    weight=w,
                    scale=0.06,
                )

        # Diagnosis inputs
        prereq_topic_ids = get_prereq_topic_ids(conn, topic_id)
        prereq_states: list[StudentTopicState] = []
        for pid in prereq_topic_ids:
            st = get_student_topic_state(conn, student_id=req.student_id, topic_id=pid)
            if st is not None:
                prereq_states.append(st)

        # Population-vs-personal blending for early-stage decisions
        pop_topic = get_population_topic_difficulty(conn, topic_id)
        topic_calibrated_difficulty = pop_topic[1] if pop_topic is not None else q.difficulty_prior
        effective_topic_state, _, _ = blended_topic_state(
            upd.new,
            population_calibrated_difficulty=topic_calibrated_difficulty,
            threshold=DEFAULT_EVIDENCE_THRESHOLD,
        )

        effective_prereq_states: list[StudentTopicState] = []
        for st in prereq_states:
            pop_pr = get_population_topic_difficulty(conn, st.topic_id)
            cal = pop_pr[1] if pop_pr is not None else topic_calibrated_difficulty
            eff, _, _ = blended_topic_state(
                st,
                population_calibrated_difficulty=cal,
                threshold=DEFAULT_EVIDENCE_THRESHOLD,
            )
            effective_prereq_states.append(eff)

        recent = list_recent_attempts_for_topic(conn, student_id=req.student_id, topic_id=topic_id, limit=20)
        # Build question map for history-based transfer/fluency detection
        qmap: dict[str, Question] = {q.id: q}
        for r in recent:
            if r.question_id not in qmap:
                qq = get_question(conn, r.question_id)
                if qq is not None:
                    qmap[qq.id] = qq

        dx = diagnose_attempt(
            attempt=att,
            question=q,
            topic_state=effective_topic_state,
            prereq_states=effective_prereq_states,
            recent_attempts=list(reversed(recent)),  # chronological order
            recent_questions=qmap,
        )

        # Next-step recommendation (allowed actions only)
        topic_ids_in_order = [t.id for t in list_topics(conn)]
        prereq_ids = get_prereq_topic_ids(conn, topic_id)
        available_qs = list_questions_by_topic(conn, topic_id)
        rec = recommend_next_step(
            latest_attempt=att,
            latest_question=q,
            diagnosis_label=dx.label,
            topic_state=effective_topic_state,
            prereq_topic_ids=prereq_ids,
            topics_in_order=topic_ids_in_order,
            available_questions=available_qs,
        )

        # Plain-English explanations (deterministic templates)
        topic_obj = get_topic(conn, topic_id)
        current_topic_title = topic_obj.title if topic_obj is not None else topic_id

        diagnosis_explanation = explain_diagnosis(
            diagnosis_label=dx.label,
            topic_state=effective_topic_state,
            topic_title=current_topic_title,
            evidence=dx.evidence,
        )

        next_topic_title = None
        if rec.next_topic_id:
            next_topic_obj = get_topic(conn, rec.next_topic_id)
            next_topic_title = next_topic_obj.title if next_topic_obj is not None else None

        rec_explanation = explain_recommendation(
            recommendation_action=rec.action,
            diagnosis_label=dx.label,
            topic_state=effective_topic_state,
            next_topic_title=next_topic_title,
        )

        return AttemptCreateResponse(
            attempt={
                **att.model_dump(),
                "submitted_at": _iso(att.submitted_at),
            },
            topic_state={
                **upd.new.model_dump(),
                "last_updated_at": _iso(upd.new.last_updated_at),
            },
            diagnosis={
                "label": dx.label,
                "summary": dx.summary,
                "evidence": dx.evidence,
                "explanation": diagnosis_explanation,
            },
            recommendation={
                "action": rec.action,
                "next_topic_id": rec.next_topic_id,
                "question_id": rec.question_id,
                "rationale": rec.rationale,
                "payload": rec.payload,
                "explanation": rec_explanation,
            },
        )
    finally:
        conn.close()


@app.get("/students/{student_id}/topic-states")
def get_student_topic_states(student_id: str) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT student_id, topic_id, mastery_score, fragility_score, fluency_score, evidence_count, last_updated_at
            FROM student_topic_state
            WHERE student_id = ?
            ORDER BY last_updated_at DESC
            """,
            (student_id,),
        ).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "student_id": r["student_id"],
                    "topic_id": r["topic_id"],
                    "mastery_score": float(r["mastery_score"]),
                    "fragility_score": float(r["fragility_score"]),
                    "fluency_score": float(r["fluency_score"]),
                    "evidence_count": int(r["evidence_count"]),
                    "last_updated_at": r["last_updated_at"],
                }
            )
        return out
    finally:
        conn.close()


def _dashboard_recommendation(conn, student_id: str) -> dict[str, Any]:
    # Minimal: choose weakest topic using *blended* effective mastery if any state exists;
    # else choose first topic in catalog.
    ensure_population_priors(conn)
    rows = conn.execute(
        """
        SELECT topic_id, mastery_score, fragility_score, fluency_score, evidence_count, last_updated_at
        FROM student_topic_state
        WHERE student_id = ?
        """,
        (student_id,),
    ).fetchall()

    if not rows:
        topics = list_topics(conn)
        if not topics:
            return {"action": "no_topics", "rationale": ["No topics available."], "next_topic_id": None}
        return {
            "action": "start_practice",
            "rationale": ["No history yet; start with the first topic."],
            "next_topic_id": topics[0].id,
        }

    # Pick the topic with lowest *effective* mastery. This makes early recommendations
    # more population-guided (when evidence is low) and later more personal-history-guided.
    weakest_row = None
    weakest_eff_mastery = None
    weakest_eff_state: Optional[StudentTopicState] = None
    for r in rows:
        topic_id = r["topic_id"]
        personal = (
            get_student_topic_state(conn, student_id=student_id, topic_id=topic_id)
            or default_state(student_id, topic_id)
        )
        pop_topic = get_population_topic_difficulty(conn, topic_id)
        cal = float(pop_topic[1]) if pop_topic is not None else 0.5
        eff, _, _ = blended_topic_state(
            personal,
            population_calibrated_difficulty=cal,
            threshold=DEFAULT_EVIDENCE_THRESHOLD,
        )
        m = float(eff.mastery_score)
        if weakest_eff_mastery is None or m < weakest_eff_mastery:
            weakest_row = r
            weakest_eff_mastery = m
            weakest_eff_state = eff

    topic_id = weakest_row["topic_id"] if weakest_row is not None else rows[0]["topic_id"]
    st_eff = weakest_eff_state or (
        get_student_topic_state(conn, student_id=student_id, topic_id=topic_id)
        or default_state(student_id, topic_id)
    )
    # Minimal: pick a first question in the weakest topic.
    available_qs = list_questions_by_topic(conn, topic_id)
    q = available_qs[0] if available_qs else None
    if q is None:
        return {
            "action": "retry_similar_question",
            "next_topic_id": topic_id,
            "question_id": None,
            "rationale": ["Weakest topic by mastery, but no questions are seeded yet."],
            "payload": {},
        }
    fake_attempt = Attempt(
        id="att_dashboard",
        student_id=student_id,
        question_id=q.id,
        topic_id=topic_id,
        correctness=False,
        time_taken_seconds=0,
        hints_used=0,
        confidence_rating=3,
        self_report_reason=None,
        submitted_at=_now(),
    )
    topic_ids_in_order = [t.id for t in list_topics(conn)]
    prereq_ids = get_prereq_topic_ids(conn, topic_id)
    rec = recommend_next_step(
        latest_attempt=fake_attempt,
        latest_question=q,
        diagnosis_label="direct_topic_weakness",
        topic_state=st_eff,
        prereq_topic_ids=prereq_ids,
        topics_in_order=topic_ids_in_order,
        available_questions=available_qs,
    )
    return {
        "action": rec.action,
        "next_topic_id": rec.next_topic_id,
        "question_id": rec.question_id,
        "rationale": rec.rationale,
        "payload": rec.payload,
    }


@app.get("/students/{student_id}/dashboard")
def get_student_dashboard(student_id: str) -> DashboardResponse:
    conn = connect()
    try:
        # Topic states
        states = conn.execute(
            """
            SELECT s.topic_id, s.mastery_score, s.fragility_score, s.fluency_score, s.evidence_count, s.last_updated_at,
                   t.title, t.cluster
            FROM student_topic_state s
            LEFT JOIN topics t ON t.id = s.topic_id
            WHERE s.student_id = ?
            """,
            (student_id,),
        ).fetchall()

        enriched = [
            {
                "topic_id": r["topic_id"],
                "title": r["title"],
                "cluster": r["cluster"],
                "mastery_score": float(r["mastery_score"]),
                "fragility_score": float(r["fragility_score"]),
                "fluency_score": float(r["fluency_score"]),
                "evidence_count": int(r["evidence_count"]),
                "last_updated_at": r["last_updated_at"],
            }
            for r in states
        ]

        strongest = sorted(enriched, key=lambda x: x["mastery_score"], reverse=True)[:5]
        weakest = sorted(enriched, key=lambda x: x["mastery_score"])[:5]
        fragile = sorted(enriched, key=lambda x: x["fragility_score"], reverse=True)[:5]

        recent = [a.model_dump() for a in list_recent_attempts(conn, student_id=student_id, limit=20)]
        for a in recent:
            a["submitted_at"] = _iso(a["submitted_at"])

        next_action = _dashboard_recommendation(conn, student_id)
        return DashboardResponse(
            strongest_topics=strongest,
            weakest_topics=weakest,
            fragile_topics=fragile,
            recent_attempts=recent,
            next_recommended_action=next_action,
        )
    finally:
        conn.close()


@app.get("/students/{student_id}/recommendation")
def get_student_recommendation(student_id: str) -> dict[str, Any]:
    conn = connect()
    try:
        return _dashboard_recommendation(conn, student_id)
    finally:
        conn.close()

