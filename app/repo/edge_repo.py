from __future__ import annotations

import sqlite3


def list_edges_for_topic(conn: sqlite3.Connection, topic_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, from_topic_id, to_topic_id, edge_type, weight
        FROM topic_edges
        WHERE from_topic_id = ? OR to_topic_id = ?
        """,
        (topic_id, topic_id),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "from_topic_id": r["from_topic_id"],
            "to_topic_id": r["to_topic_id"],
            "edge_type": r["edge_type"],
            "weight": float(r["weight"]),
        }
        for r in rows
    ]


def get_prereq_topic_ids(conn: sqlite3.Connection, topic_id: str) -> list[str]:
    # prerequisite edge: prereq -> topic
    rows = conn.execute(
        """
        SELECT from_topic_id
        FROM topic_edges
        WHERE to_topic_id = ? AND edge_type = 'prerequisite'
        ORDER BY weight DESC
        """,
        (topic_id,),
    ).fetchall()
    return [r["from_topic_id"] for r in rows]

