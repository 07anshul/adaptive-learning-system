# Adaptive Learning System (Demo)

This repository is a **fast demo** focused on transparent, rule-based adaptive learning behaviors.

## Demo constraints (important)

- **Speed over polish**: 1–2 day demo, not production-grade.
- **Simple + interpretable**: keep logic understandable (no black boxes).
- **No machine learning**: do not add ML models.
- **Must work without topic edges**: topic graph relationships are optional; the system should still run if none exist.
- **Avoid over-engineering**: if unsure between simple vs complex → choose simple.

## What this demo should demonstrate

- Student-topic scoring
- Fragile understanding detection
- Diagnosis of likely cause
- Next-step recommendation

## Handy commands (demo setup)

### Create venv + install deps

```bash
python -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt
```

### Initialize SQLite DB schema

```bash
.venv/bin/python scripts/init_db.py
```

### Seed Grade 7 Mathematics topic graph

```bash
.venv/bin/python scripts/seed_graph.py
```

### Seed Grade 7 Mathematics questions (first 12 topics)

```bash
.venv/bin/python scripts/seed_questions.py
```

### Quick sanity check (counts)

```bash
.venv/bin/python -c "import sqlite3; c=sqlite3.connect('db/demo.sqlite3'); print('topics', c.execute('select count(*) from topics').fetchone()[0]); print('edges', c.execute('select count(*) from topic_edges').fetchone()[0])"
```

### Run the demo API

```bash
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

### Open the demo UI

- Home: `http://127.0.0.1:8000/`
- Student dashboard: `http://127.0.0.1:8000/ui/students/stu_demo/dashboard`
- Topics list: `http://127.0.0.1:8000/ui/topics`

### Key files

- `db/schema.sql`: SQLite schema
- `data/grade7_math_graph.json`: Grade 7 topics + edges seed
- `scripts/init_db.py`: create `db/demo.sqlite3` from schema
- `scripts/seed_graph.py`: load seed JSON into SQLite
- `app/main.py`: FastAPI demo API

