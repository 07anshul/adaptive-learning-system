from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.db import connect, init_db
from app.repo.population_repo import ensure_population_priors

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
                "topic_stats": [_to_dict(r) for r in topic_rows],
                "question_stats": [_to_dict(r) for r in question_rows],
            },
        )
    finally:
        conn.close()

