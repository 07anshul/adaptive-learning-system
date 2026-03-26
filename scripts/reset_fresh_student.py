from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.scoring import default_state  # noqa: E402
from app.db import connect, init_db  # noqa: E402
from app.repo.population_repo import ensure_population_priors  # noqa: E402
from app.repo.student_state_repo import upsert_student_topic_state  # noqa: E402
from app.repo.topic_repo import list_topics  # noqa: E402


FRESH_ID = "stu_fresh"


def main() -> None:
    conn = connect()
    init_db(conn)
    ensure_population_priors(conn)

    now = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")

    with conn:
        # Ensure student exists
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, display_name, created_at)
            VALUES (?, ?, ?)
            """,
            (FRESH_ID, "Fresh demo student (no history)", now),
        )
        # Clear personal history/state
        conn.execute("DELETE FROM attempts WHERE student_id = ?", (FRESH_ID,))
        conn.execute("DELETE FROM student_topic_state WHERE student_id = ?", (FRESH_ID,))

        # Seed neutral default states (no evidence) so UI can show "student-specific mastery"
        for t in list_topics(conn):
            st = default_state(FRESH_ID, t.id)
            upsert_student_topic_state(conn, st)

    print("OK: reset fresh student with neutral personal states and no attempts:", FRESH_ID)


if __name__ == "__main__":
    main()

