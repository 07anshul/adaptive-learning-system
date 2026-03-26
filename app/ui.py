from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.diagnosis import diagnose_attempt
from app.core.next_step import recommend_next_step
from app.core.explanations import explain_diagnosis, explain_recommendation
from app.core.scoring import default_state, update_student_topic_state
from app.core.blending import blended_topic_state, DEFAULT_EVIDENCE_THRESHOLD
from app.db import connect, init_db
from app.models.domain import Attempt, Question, StudentTopicState
from app.repo.attempt_repo import insert_attempt, list_recent_attempts
from app.repo.edge_repo import get_prereq_topic_ids, list_edges_for_topic, get_encompassing_parent_ids, get_edge_weight
from app.repo.question_repo import get_question, list_questions_by_topic
from app.repo.population_repo import (
    ensure_population_priors,
    get_population_question_difficulty,
    get_population_topic_difficulty,
    update_population_from_attempt,
)
from app.repo.student_state_repo import get_student_topic_state, upsert_student_topic_state
from app.repo.topic_repo import get_topic, list_topics
from app.repo.state_propagation import apply_soft_neighbor_update


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def topic_status_label(state: Optional[StudentTopicState]) -> str:
    if state is None:
        return "Unseen"
    # Fresh/zero-evidence topics should not be labeled as Weak/Strong yet.
    # We seed neutral defaults for demo convenience; treat them as "Unseen" until the student has evidence.
    if int(getattr(state, "evidence_count", 0)) <= 0:
        return "Unseen"
    m = state.mastery_score
    f = state.fragility_score
    # Demo-friendly thresholds (tuned so simulation profiles visibly differ):
    # - Weak: low mastery
    # - Fragile: not weak, but unstable (high fragility)
    # - Strong: good mastery + not fragile
    if m <= 0.35:
        return "Weak"
    if f >= 0.60:
        return "Fragile"
    if m >= 0.65 and f <= 0.50:
        return "Strong"
    return "Okay"


def _ensure_student_exists(conn, student_id: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO students (id, display_name, created_at)
        VALUES (?, ?, ?)
        """,
        (student_id, f"Student {student_id}", _iso(_now())),
    )


def _list_students(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, display_name
        FROM students
        ORDER BY id ASC
        """
    ).fetchall()
    out = [{"id": r["id"], "display_name": r["display_name"]} for r in rows]
    # Ensure fresh student is always visible even if not inserted yet.
    if not any(x["id"] == "stu_fresh" for x in out):
        out.insert(0, {"id": "stu_fresh", "display_name": "Fresh demo student (no history)"})
    return out


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
        },
    )


@router.get("/ui/topics", response_class=HTMLResponse)
def ui_topics(request: Request) -> HTMLResponse:
    conn = connect()
    try:
        init_db(conn)
        topics = list_topics(conn)
        # edge counts (sparse graph visible)
        edge_counts = {}
        for t in topics:
            edge_counts[t.id] = len(list_edges_for_topic(conn, t.id))
        return templates.TemplateResponse(
            "topics.html",
            {
                "request": request,
                "topics": topics,
                "edge_counts": edge_counts,
            },
        )
    finally:
        conn.close()


@router.post("/ui/select-student")
def ui_select_student(student_id: str = Form(...)) -> RedirectResponse:
    return RedirectResponse(url=f"/ui/students/{student_id}/dashboard", status_code=303)


@router.get("/ui/topics/{topic_id}", response_class=HTMLResponse)
def ui_topic_detail(request: Request, topic_id: str) -> HTMLResponse:
    conn = connect()
    try:
        init_db(conn)
        t = get_topic(conn, topic_id)
        if t is None:
            raise HTTPException(status_code=404, detail="topic_not_found")
        edges = list_edges_for_topic(conn, topic_id)
        questions = list_questions_by_topic(conn, topic_id)
        return templates.TemplateResponse(
            "topic_detail.html",
            {
                "request": request,
                "topic": t,
                "edges": edges,
                "questions": questions,
            },
        )
    finally:
        conn.close()


@router.get("/ui/students/{student_id}/dashboard", response_class=HTMLResponse)
def ui_student_dashboard(request: Request, student_id: str) -> HTMLResponse:
    conn = connect()
    try:
        init_db(conn)
        ensure_population_priors(conn)
        _ensure_student_exists(conn, student_id)

        topics = list_topics(conn)
        states_by_topic: dict[str, StudentTopicState] = {}
        for t in topics:
            st = get_student_topic_state(conn, student_id=student_id, topic_id=t.id)
            if st is not None:
                states_by_topic[t.id] = st

        enriched = []
        for t in topics:
            st = states_by_topic.get(t.id)
            enriched.append(
                {
                    "topic": t,
                    "state": st,
                    "status": topic_status_label(st),
                }
            )

        def mastery_key(x):
            st = x["state"]
            return st.mastery_score if st else -1.0

        strongest = sorted([x for x in enriched if x["state"]], key=mastery_key, reverse=True)[:5]
        weakest = sorted([x for x in enriched if x["state"]], key=mastery_key)[:5]
        fragile = sorted([x for x in enriched if x["state"]], key=lambda x: x["state"].fragility_score if x["state"] else -1.0, reverse=True)[:5]

        recent = list_recent_attempts(conn, student_id=student_id, limit=12)

        # Minimal next action: if any states, choose weakest; else first topic.
        if weakest:
            next_topic_id = weakest[0]["topic"].id
        else:
            next_topic_id = topics[0].id if topics else None

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "student_id": student_id,
                "student_list": _list_students(conn),
                "topics": topics,
                "states_by_topic": states_by_topic,
                "enriched": enriched,
                "strongest": strongest,
                "weakest": weakest,
                "fragile": fragile,
                "recent_attempts": recent,
                "next_topic_id": next_topic_id,
                "is_fresh": student_id == "stu_fresh",
            },
        )
    finally:
        conn.close()


def _pick_question(questions: list[Question]) -> Optional[Question]:
    if not questions:
        return None
    # Prefer higher diagnostic value so the demo shows behavior quickly.
    questions = sorted(questions, key=lambda q: (-q.diagnostic_value, q.difficulty_prior))
    top = questions[:3] if len(questions) >= 3 else questions
    return random.choice(top)


@router.get("/ui/students/{student_id}/practice/{topic_id}", response_class=HTMLResponse)
def ui_practice(request: Request, student_id: str, topic_id: str, question_id: Optional[str] = None) -> HTMLResponse:
    conn = connect()
    try:
        init_db(conn)
        _ensure_student_exists(conn, student_id)
        topic = get_topic(conn, topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="topic_not_found")

        qs = list_questions_by_topic(conn, topic_id)
        if not qs:
            return templates.TemplateResponse(
                "practice.html",
                {
                    "request": request,
                    "student_id": student_id,
                    "topic": topic,
                    "question": None,
                    "feedback": None,
                    "topic_state": get_student_topic_state(conn, student_id=student_id, topic_id=topic_id),
                    "status": topic_status_label(get_student_topic_state(conn, student_id=student_id, topic_id=topic_id)),
                },
            )

        q = get_question(conn, question_id) if question_id else None
        if q is None:
            q = _pick_question(qs)

        st = get_student_topic_state(conn, student_id=student_id, topic_id=topic_id)
        return templates.TemplateResponse(
            "practice.html",
            {
                "request": request,
                "student_id": student_id,
                "topic": topic,
                "question": q,
                "feedback": None,
                "topic_state": st,
                "status": topic_status_label(st),
            },
        )
    finally:
        conn.close()


@router.post("/ui/attempts", response_class=HTMLResponse)
def ui_submit_attempt(
    request: Request,
    student_id: str = Form(...),
    topic_id: str = Form(...),
    question_id: str = Form(...),
    answer: str = Form(""),
    time_taken_seconds: int = Form(30),
    hints_used: int = Form(0),
    confidence_rating: int = Form(3),
) -> HTMLResponse:
    conn = connect()
    try:
        init_db(conn)
        ensure_population_priors(conn)
        _ensure_student_exists(conn, student_id)

        q = get_question(conn, question_id)
        if q is None:
            raise HTTPException(status_code=404, detail="question_not_found")
        # Use population-calibrated difficulty as the active prior.
        pop_qd = get_population_question_difficulty(conn, q.id)
        if pop_qd is not None:
            q = q.model_copy(update={"difficulty_prior": pop_qd[1]})
        topic = get_topic(conn, topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="topic_not_found")

        # Simple correctness check for demo: string-compare trimmed answers.
        correctness = str(answer).strip() == str(q.correct_answer).strip()

        att = Attempt(
            id=f"att_{uuid.uuid4().hex[:12]}",
            student_id=student_id,
            question_id=q.id,
            topic_id=topic_id,
            correctness=correctness,
            time_taken_seconds=max(0, int(time_taken_seconds)),
            hints_used=max(0, int(hints_used)),
            confidence_rating=int(confidence_rating),
            self_report_reason=None,
            submitted_at=_now(),
        )
        with conn:
            insert_attempt(conn, att)

        prev_state = get_student_topic_state(conn, student_id=student_id, topic_id=topic_id)
        upd = update_student_topic_state(prev_state, attempt=att, question=q)
        with conn:
            upsert_student_topic_state(conn, upd.new)

        # Update population calibration (global, not tied to this student)
        with conn:
            update_population_from_attempt(conn, attempt=att, question=q)

        # Optional conservative neighbor-topic propagation (only if edges exist)
        with conn:
            prereqs = get_prereq_topic_ids(conn, topic_id)
            for pid in prereqs:
                w = get_edge_weight(conn, pid, topic_id, "prerequisite")
                apply_soft_neighbor_update(
                    conn,
                    student_id=student_id,
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
                    student_id=student_id,
                    topic_id=parent_id,
                    mastery_delta=upd.mastery_delta,
                    fragility_delta=upd.fragility_delta,
                    fluency_delta=upd.fluency_delta,
                    weight=w,
                    scale=0.06,
                )

        prereq_ids = get_prereq_topic_ids(conn, topic_id)
        prereq_states = []
        for pid in prereq_ids:
            st = get_student_topic_state(conn, student_id=student_id, topic_id=pid)
            if st is not None:
                prereq_states.append(st)

        # Population-vs-personal blending for early-stage decisions (engine-only)
        pop_topic = get_population_topic_difficulty(conn, topic_id)
        topic_calibrated_difficulty = pop_topic[1] if pop_topic is not None else q.difficulty_prior
        effective_topic_state, _, _ = blended_topic_state(
            upd.new,
            population_calibrated_difficulty=topic_calibrated_difficulty,
            threshold=DEFAULT_EVIDENCE_THRESHOLD,
        )

        effective_prereq_states = []
        for st in prereq_states:
            pop_pr = get_population_topic_difficulty(conn, st.topic_id)
            cal = pop_pr[1] if pop_pr is not None else topic_calibrated_difficulty
            eff, _, _ = blended_topic_state(
                st,
                population_calibrated_difficulty=cal,
                threshold=DEFAULT_EVIDENCE_THRESHOLD,
            )
            effective_prereq_states.append(eff)

        # For diagnosis history, reuse recent attempts in this topic.
        recent = list_recent_attempts(conn, student_id=student_id, limit=25)
        qmap = {q.id: q}
        for r in recent:
            if r.question_id not in qmap:
                qq = get_question(conn, r.question_id)
                if qq:
                    qmap[qq.id] = qq

        dx = diagnose_attempt(
            attempt=att,
            question=q,
            topic_state=effective_topic_state,
            prereq_states=effective_prereq_states,
            recent_attempts=list(reversed(recent)),
            recent_questions=qmap,
        )

        topic_ids_in_order = [t.id for t in list_topics(conn)]
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

        diagnosis_expl = explain_diagnosis(
            diagnosis_label=dx.label,
            topic_state=effective_topic_state,
            topic_title=topic.title if topic is not None else upd.new.topic_id,
            evidence=dx.evidence,
        )
        rec_expl = explain_recommendation(
            recommendation_action=rec.action,
            diagnosis_label=dx.label,
            topic_state=effective_topic_state,
            next_topic_title=topic.title if rec.next_topic_id == topic.id else None,
        )

        feedback = {
            "is_correct": correctness,
            "correct_answer": q.correct_answer,
            "explanation_text": q.explanation_text,
            "hint_text": q.hint_text,
            "diagnosis_label": dx.label,
            "diagnosis_summary": dx.summary,
            "diagnosis_explanation": diagnosis_expl,
            "recommendation": rec,
            "recommendation_explanation": rec_expl,
        }

        return templates.TemplateResponse(
            "practice.html",
            {
                "request": request,
                "student_id": student_id,
                "topic": topic,
                "question": q,
                "feedback": feedback,
                "topic_state": upd.new,
                "status": topic_status_label(upd.new),
            },
        )
    finally:
        conn.close()

