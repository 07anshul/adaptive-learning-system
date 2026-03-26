from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import connect, init_db  # noqa: E402
from app.repo.population_repo import ensure_population_priors  # noqa: E402


SEED_PATH = Path("data/grade7_math_graph.json")


def _loads_json_array(text: str) -> list:
    if not text:
        return []
    return json.loads(text)


def seed_topics_and_edges(seed_path: Path = SEED_PATH) -> None:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    topics = payload.get("topics", [])
    edges = payload.get("edges", [])

    conn = connect()
    init_db(conn)

    with conn:
        for t in topics:
            conn.execute(
                """
                INSERT OR REPLACE INTO topics
                (id, title, description, cluster, grade_level, order_index, difficulty_prior, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    t["id"],
                    t["title"],
                    t["description"],
                    t["cluster"],
                    int(t.get("grade_level", 7)),
                    int(t.get("order_index", 0)),
                    float(t["difficulty_prior"]),
                    json.dumps(t.get("tags", [])),
                ),
            )

        for e in edges:
            conn.execute(
                """
                INSERT OR REPLACE INTO topic_edges
                (id, from_topic_id, to_topic_id, edge_type, weight)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    e["id"],
                    e["source"],
                    e["target"],
                    e["edge_type"],
                    float(e.get("weight", 0.5)),
                ),
            )


def main() -> None:
    seed_topics_and_edges()
    # Ensure population priors exist after topic insert.
    conn = connect()
    init_db(conn)
    with conn:
        ensure_population_priors(conn)
    conn.close()
    print(f"OK: seeded topics/edges from {SEED_PATH}")


if __name__ == "__main__":
    main()

