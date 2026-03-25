from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import connect, init_db  # noqa: E402


def main() -> None:
    conn = connect()
    init_db(conn)
    print("OK: initialized db/demo.sqlite3 from db/schema.sql")


if __name__ == "__main__":
    main()

