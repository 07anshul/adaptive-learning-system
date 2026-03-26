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


def get_encompassing_parent_ids(conn: sqlite3.Connection, topic_id: str) -> list[str]:
    # encompassing edge: broad -> specific, so parents are from_topic_id where to_topic_id = topic_id
    rows = conn.execute(
        """
        SELECT from_topic_id
        FROM topic_edges
        WHERE to_topic_id = ? AND edge_type = 'encompassing'
        ORDER BY weight DESC
        """,
        (topic_id,),
    ).fetchall()
    return [r["from_topic_id"] for r in rows]


def get_edge_weight(conn: sqlite3.Connection, from_topic_id: str, to_topic_id: str, edge_type: str) -> float:
    r = conn.execute(
        """
        SELECT weight
        FROM topic_edges
        WHERE from_topic_id = ? AND to_topic_id = ? AND edge_type = ?
        """,
        (from_topic_id, to_topic_id, edge_type),
    ).fetchone()
    return float(r["weight"]) if r is not None else 0.0

