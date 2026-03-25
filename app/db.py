from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("db/demo.sqlite3")
DEFAULT_SCHEMA_PATH = Path("db/schema.sql")


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(
    conn: sqlite3.Connection,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> None:
    schema_sql = schema_path.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()

