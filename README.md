# Adaptive Learning System

## Overview

This project is an adaptive learning engine that models student understanding at the topic level and recommends what to do next.

Instead of tracking only right/wrong outcomes, it uses multiple learning signals from each attempt:

- correctness
- time taken
- hints used
- confidence

The system updates student knowledge state continuously and produces diagnosis and next-step guidance based on recent behavior.

What makes this different is that it explicitly models **fragile understanding**, not just whether an answer is correct.

## Problem Statement

Most traditional practice systems rely heavily on correctness alone. This creates blind spots:

- a student can be correct but still fragile (slow, uncertain, hint-dependent)
- a wrong answer may come from prerequisite weakness, not only current-topic weakness
- next-step practice can become repetitive and not personalized enough

An adaptive system should detect these patterns and respond with targeted support.

## Solution Approach

The system combines five practical ideas:

- **Per-student topic state** to represent current understanding over time
- **Multi-signal attempt analysis** (correctness, time, hints, confidence)
- **Topic graph support** for prerequisite-aware diagnosis when relationships exist
- **Population + individual blending** for cold start and gradual personalization
- **Adaptive recommendation engine** for actionable next steps after each attempt

This keeps learning decisions interpretable while supporting richer adaptation than right/wrong scoring.
Core system loop: **attempt → state update → diagnosis → recommendation**.

## Core Concepts

- **Mastery**
  - A score for how reliably a student can solve questions in a topic.
  - Higher mastery means stronger topic command.

- **Fragility**
  - A score for how unstable the understanding is, even when answers are sometimes correct.
  - Higher fragility means understanding is less stable and may break under variation; this is a key signal for deciding whether to reinforce or progress.

- **Fluency**
  - A score for speed and effort efficiency in a topic.
  - Higher fluency means the student is more efficient and consistent.

- **Evidence Count**
  - Number of attempts contributing to a student’s state for a topic.
  - More evidence means the system trusts student-specific behavior more.

- **Population Prior vs Student-Specific State**
  - Population priors provide calibrated expectations for new/low-evidence learners.
  - Student-specific state captures personal learning trajectory and increasingly dominates with evidence.

## How It Works Internally

### Student State Update

After each attempt, the engine updates topic-level student state:

- mastery
- fragility
- fluency
- evidence_count

Update signals include:

- correctness
- time taken vs expected time
- hints used
- confidence
- question difficulty/load metadata

Updates are incremental, so the state changes gradually as evidence accumulates.

### Diagnosis Engine

The diagnosis layer assigns a likely cause label for current performance, such as:

- direct topic weakness
- fragile understanding
- prerequisite gap (if graph evidence exists)
- fluency issue
- transfer issue
- confidence issue

It uses current topic state, recent attempts, and graph context when available.

### Recommendation Engine

The recommendation layer chooses the next action from a fixed action set, for example:

- retry a similar question
- assign lower-transfer or bridge practice
- assign fluency-focused practice
- review prerequisite topic
- advance to next topic

Selection depends on diagnosis, current state, recent evidence, and available questions.

### Population + Individual Blending

The engine uses population-calibrated priors for low-evidence learners and transitions toward student-specific state as evidence grows.

In practice:

- early interactions are guided by calibrated priors for robustness
- personal performance increasingly drives decisions as attempts accumulate

Lightweight blending logic (high-level):

- `personal_weight ≈ min(1, evidence_count / threshold)`
- `population_weight ≈ 1 - personal_weight`

So the system behaves like this:

- **Early stage:** low evidence means population priors dominate, which stabilizes cold-start decisions.
- **Later stage:** higher evidence shifts weight to student-specific behavior, so recommendations reflect that student’s own pattern.

Signals influence state in intuitive ways:

- **Mastery** rises with clean correct performance (correct + reasonable time + low hints + good confidence).
- **Fragility** rises when performance is shaky (slow, hint-heavy, uncertain) and falls with stable clean success.
- **Fluency** improves with faster, consistent correct responses and drops when responses are slow or effort-heavy.

## Key Calculations (High-Level)

- **Mastery** increases with consistent correct performance, especially when confidence is strong and hint dependence is low (for example: correct + confidence 4/5 + 0 hints).
- **Fragility** increases with unstable signals (for example: correct but very slow, hint-heavy, or low confidence) and decreases with clean, consistent success.
- **Fluency** improves with faster, low-friction correct performance and degrades with slow/error-prone behavior (for example: repeated high time-vs-expected).
- **Recommendations** are threshold- and rule-driven, using diagnosis + topic state + recent evidence.
- **Progression decisions** are based on readiness patterns, not correctness alone.

## What This Enables

- Earlier detection of unstable understanding before it turns into repeated failure.
- Next-step guidance that can differentiate between reinforcement, fluency practice, and progression.
- A practical path from cold-start learners to individualized sequencing as student evidence grows.

## Project Structure

- **`app/main.py`**
  - API entrypoint and attempt-processing pipeline.

- **`app/ui.py`**
  - Server-rendered UI routes for dashboard, practice, and feedback flow.

- **`app/core/scoring.py`**
  - Student-topic state update logic.

- **`app/core/diagnosis.py`**
  - Rule-based diagnosis engine.

- **`app/core/next_step.py`**
  - Next-step recommendation logic.

- **`app/core/blending.py`**
  - Population + personal blending functions.

- **`app/core/explanations.py`**
  - Deterministic plain-English explanation templates.

- **`app/repo/`**
  - Data access for topics, questions, attempts, state, graph edges, and population stats.

- **`db/schema.sql`**
  - SQLite schema.

- **`scripts/`**
  - DB init, graph/question seeding, student simulation, and fresh-student reset.

- **`data/`**
  - Topic graph and generated question seed files.

## Running the Project

### 1) Install dependencies

```bash
python -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt
```

### 2) Prepare database and seed data

```bash
rm -f db/demo.sqlite3
.venv/bin/python scripts/init_db.py
.venv/bin/python scripts/seed_graph.py
.venv/bin/python scripts/generate_questions_all.py
.venv/bin/python scripts/seed_questions_all.py
.venv/bin/python scripts/simulate_students.py
.venv/bin/python scripts/reset_fresh_student.py
```

### 3) Run the server

```bash
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

### 4) Open key routes

- Home: `http://127.0.0.1:8000/`
- Fresh student dashboard: `http://127.0.0.1:8000/ui/students/stu_fresh/dashboard`
- Topics: `http://127.0.0.1:8000/ui/topics`
- Internal analytics: `http://127.0.0.1:8000/internal/analytics`

## Testing the System

Use this sequence to verify behavior end-to-end and confirm that adaptation is driven by learning signals, not only correctness.
The goal is to validate both technical correctness and instructional behavior (state movement, diagnosis quality, recommendation quality).

### Fresh student flow (`stu_fresh`)

1. Open fresh dashboard: `/ui/students/stu_fresh/dashboard`
2. Confirm no personal attempts are listed initially.
3. Start practice on a topic.
4. Submit attempts with different patterns:
   - correct + fast + high confidence + no hints
   - correct but slow/low confidence
   - wrong with/without hints
5. Observe after-attempt panel for:
   - updated state
   - diagnosis
   - recommendation

### Simulated student flow

1. Switch to seeded students from the dashboard selector.
2. Compare strongest/weakest/fragile topic patterns across profiles.
3. Verify recommendations differ by student state.

### Analytics validation

Open `/internal/analytics` and verify:

- state-driven learning-efficiency metrics update after new attempts
- recommendation effectiveness section reflects stored/recomputed action sources
- population and student signals remain internal/admin-facing

## Notes

- The platform is designed so personalization improves with additional learner data.
- The modular pipeline (state update, diagnosis, recommendation, blending) supports future model upgrades while keeping decision behavior explainable.

