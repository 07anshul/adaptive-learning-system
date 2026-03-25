from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.diagnosis import diagnose_attempt
from app.core.recommend import Recommendation, recommend_next
from app.core.scoring import default_state, update_student_topic_state
from app.db import connect, init_db
from app.models.domain import Attempt, Question, StudentTopicState
from app.repo.attempt_repo import (
    insert_attempt,
    list_recent_attempts,
    list_recent_attempts_for_topic,
)
from app.repo.edge_repo import get_prereq_topic_ids, list_edges_for_topic
from app.repo.question_repo import get_question, list_questions_by_topic
from app.repo.student_state_repo import get_student_topic_state, upsert_student_topic_state
from app.repo.topic_repo import get_topic, list_topics


app = FastAPI(title="Adaptive Learning System (Demo API)")


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

        q = get_question(conn, req.question_id)
        if q is None:
            raise HTTPException(status_code=404, detail="question_not_found")

        topic_id = req.topic_id or q.topic_id

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

        # Diagnosis inputs
        prereq_topic_ids = get_prereq_topic_ids(conn, topic_id)
        prereq_states: list[StudentTopicState] = []
        for pid in prereq_topic_ids:
            st = get_student_topic_state(conn, student_id=req.student_id, topic_id=pid)
            if st is not None:
                prereq_states.append(st)

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
            topic_state=upd.new,
            prereq_states=prereq_states,
            recent_attempts=list(reversed(recent)),  # chronological order
            recent_questions=qmap,
        )

        # Recommendation
        # For demo simplicity, suggest questions from the same topic if present.
        qids = [qq.id for qq in list_questions_by_topic(conn, topic_id)]
        weakest_prereq_id = None
        if prereq_states:
            weakest_prereq_id = min(prereq_states, key=lambda s: s.mastery_score).topic_id

        rec = recommend_next(
            topic_id=topic_id,
            diagnosis=dx,
            topic_state=upd.new,
            weakest_prereq_topic_id=weakest_prereq_id,
            available_question_ids=qids,
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
            },
            recommendation={
                "next_topic_id": rec.next_topic_id,
                "action": rec.action,
                "rationale": rec.rationale,
                "suggested_question_ids": rec.suggested_question_ids,
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
    # Minimal: choose weakest topic if any state exists; else choose first topic in catalog.
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

    weakest = min(rows, key=lambda r: float(r["mastery_score"]))
    topic_id = weakest["topic_id"]
    st = get_student_topic_state(conn, student_id=student_id, topic_id=topic_id) or default_state(student_id, topic_id)
    # Fake a minimal diagnosis for dashboard-only rec
    dx = {"label": "direct_topic_weakness", "summary": "Weakest topic by mastery.", "evidence": {}}
    qids = [qq.id for qq in list_questions_by_topic(conn, topic_id)]
    rec = recommend_next(
        topic_id=topic_id,
        diagnosis=type("Dx", (), dx)(),  # minimal duck-typed object
        topic_state=st,
        weakest_prereq_topic_id=None,
        available_question_ids=qids,
    )
    return {
        "next_topic_id": rec.next_topic_id,
        "action": rec.action,
        "rationale": rec.rationale,
        "suggested_question_ids": rec.suggested_question_ids,
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

