from __future__ import annotations

import json
import sqlite3
from typing import Optional

from app.models.domain import Topic


def list_topics(conn: sqlite3.Connection) -> list[Topic]:
    rows = conn.execute(
        """
        SELECT id, title, description, cluster, grade_level, order_index, difficulty_prior, tags_json
        FROM topics
        ORDER BY order_index ASC
        """
    ).fetchall()
    out: list[Topic] = []
    for r in rows:
        out.append(
            Topic(
                id=r["id"],
                title=r["title"],
                description=r["description"],
                cluster=r["cluster"],
                grade_level=int(r["grade_level"]),
                order_index=int(r["order_index"]),
                difficulty_prior=float(r["difficulty_prior"]),
                tags=json.loads(r["tags_json"] or "[]"),
            )
        )
    return out


def get_topic(conn: sqlite3.Connection, topic_id: str) -> Optional[Topic]:
    r = conn.execute(
        """
        SELECT id, title, description, cluster, grade_level, order_index, difficulty_prior, tags_json
        FROM topics
        WHERE id = ?
        """,
        (topic_id,),
    ).fetchone()
    if r is None:
        return None
    return Topic(
        id=r["id"],
        title=r["title"],
        description=r["description"],
        cluster=r["cluster"],
        grade_level=int(r["grade_level"]),
        order_index=int(r["order_index"]),
        difficulty_prior=float(r["difficulty_prior"]),
        tags=json.loads(r["tags_json"] or "[]"),
    )

