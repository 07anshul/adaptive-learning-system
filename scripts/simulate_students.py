from __future__ import annotations

import math
import random
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.scoring import ScoringParams, expected_time_seconds, update_student_topic_state  # noqa: E402
from app.db import connect, init_db  # noqa: E402
from app.models.domain import Attempt, Question, StudentTopicState  # noqa: E402
from app.repo.attempt_repo import insert_attempt  # noqa: E402
from app.repo.question_repo import list_questions_by_topic  # noqa: E402
from app.repo.student_state_repo import get_student_topic_state, upsert_student_topic_state  # noqa: E402
from app.repo.topic_repo import list_topics  # noqa: E402


# ----------------------------
# 1) Fake student profiles
# ----------------------------


@dataclass(frozen=True)
class StudentProfile:
    profile_id: str
    display_name: str

    # Ability: higher => more likely correct
    base_ability: float  # ~[-1.0, +1.0]

    # Speed: multiplies expected time (lower=faster)
    speed_multiplier: float  # e.g. 0.75 fast, 1.4 slow

    # Confidence tendency: shifts confidence up/down
    confidence_bias: float  # e.g. -1.0 low confidence, +0.5 high

    # Hint tendency: expected hints used
    hint_rate: float  # e.g. 0.1 low, 1.2 high

    # Extra sensitivity factors
    transfer_penalty: float  # hurts high-transfer questions
    procedural_bonus: float  # helps procedural-heavy questions
    conceptual_bonus: float  # helps conceptual-heavy questions

    # Topic-specific modifiers (topic_id -> ability delta)
    topic_ability_delta: Dict[str, float]


def build_profiles() -> List[StudentProfile]:
    """
    Profiles chosen to make dashboards visibly different with our seeded topics/questions.
    """
    fractions_topics = {"t_fraction_concepts", "t_simplify_fractions", "t_fraction_add_sub_unlike"}

    def deltas_for_weak_fractions() -> Dict[str, float]:
        return {t: -0.9 for t in fractions_topics}

    return [
        StudentProfile(
            profile_id="stu_strong_overall",
            display_name="Aarav (strong overall)",
            base_ability=2.10,
            speed_multiplier=0.8,
            confidence_bias=0.6,
            hint_rate=0.05,
            transfer_penalty=0.10,
            procedural_bonus=0.10,
            conceptual_bonus=0.10,
            topic_ability_delta={},
        ),
        StudentProfile(
            profile_id="stu_weak_in_fractions",
            display_name="Diya (weak in fractions)",
            base_ability=0.25,
            speed_multiplier=1.05,
            confidence_bias=-0.2,
            hint_rate=0.35,
            transfer_penalty=0.15,
            procedural_bonus=0.05,
            conceptual_bonus=0.00,
            topic_ability_delta=deltas_for_weak_fractions(),
        ),
        StudentProfile(
            profile_id="stu_good_but_slow",
            display_name="Kabir (good but slow)",
            base_ability=0.55,
            speed_multiplier=1.55,
            confidence_bias=0.10,
            hint_rate=0.15,
            transfer_penalty=0.10,
            procedural_bonus=0.05,
            conceptual_bonus=0.05,
            topic_ability_delta={},
        ),
        StudentProfile(
            profile_id="stu_low_confidence",
            display_name="Meera (low confidence)",
            base_ability=0.40,
            speed_multiplier=1.10,
            confidence_bias=-0.9,
            hint_rate=0.25,
            transfer_penalty=0.10,
            procedural_bonus=0.05,
            conceptual_bonus=0.05,
            topic_ability_delta={},
        ),
        StudentProfile(
            profile_id="stu_transfer_weak",
            display_name="Rohan (transfer-weak)",
            base_ability=0.45,
            speed_multiplier=1.10,
            confidence_bias=-0.1,
            hint_rate=0.20,
            transfer_penalty=0.70,
            procedural_bonus=0.10,
            conceptual_bonus=0.00,
            topic_ability_delta={},
        ),
        StudentProfile(
            profile_id="stu_hint_dependent",
            display_name="Sara (hint-dependent)",
            base_ability=0.35,
            speed_multiplier=1.20,
            confidence_bias=-0.3,
            hint_rate=1.20,
            transfer_penalty=0.20,
            procedural_bonus=0.05,
            conceptual_bonus=0.00,
            topic_ability_delta={},
        ),
        StudentProfile(
            profile_id="stu_integer_strong",
            display_name="Ishaan (integers strong)",
            base_ability=0.30,
            speed_multiplier=1.05,
            confidence_bias=0.10,
            hint_rate=0.25,
            transfer_penalty=0.15,
            procedural_bonus=0.10,
            conceptual_bonus=0.00,
            topic_ability_delta={
                "t_integer_abs_value": +0.6,
                "t_integer_add_sub": +0.6,
                "t_integer_mult_div": +0.6,
            },
        ),
        StudentProfile(
            profile_id="stu_percent_struggles",
            display_name="Nisha (percent struggles)",
            base_ability=0.35,
            speed_multiplier=1.15,
            confidence_bias=-0.2,
            hint_rate=0.35,
            transfer_penalty=0.25,
            procedural_bonus=0.05,
            conceptual_bonus=0.00,
            topic_ability_delta={
                "t_percent_concepts": -0.6,
                "t_percent_of_quantity": -0.8,
            },
        ),
    ]


# ----------------------------
# 2) Attempt generation logic
# ----------------------------


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def ability_for(profile: StudentProfile, topic_id: str) -> float:
    return profile.base_ability + profile.topic_ability_delta.get(topic_id, 0.0)


def probability_correct(profile: StudentProfile, q: Question) -> float:
    """
    Interpretable probability model (NOT ML training; just a hand-tuned simulator):
    - harder questions reduce probability
    - transfer-heavy questions reduce probability (especially for transfer-weak profile)
    - procedural/conceptual loads interact with bonuses
    """
    a = ability_for(profile, q.topic_id)
    # Difficulty and loads as penalties
    diff = q.difficulty_prior
    transfer = q.transfer_load
    proc = q.procedural_load
    conc = q.conceptual_load

    # Simple linear score then sigmoid.
    score = (
        1.8 * a
        - 1.2 * diff
        - profile.transfer_penalty * (0.9 * transfer)
        + profile.procedural_bonus * (0.6 * proc)
        + profile.conceptual_bonus * (0.6 * conc)
    )
    # Clamp to sane range
    p = sigmoid(score)
    return max(0.05, min(0.95, p))


def sample_hints_used(profile: StudentProfile, is_correct: bool, q: Question, rng: random.Random) -> int:
    # Hint-dependent students use more hints; hard/transfer items slightly increase hints.
    lam = profile.hint_rate + 0.6 * q.difficulty_prior + 0.4 * q.transfer_load
    if not is_correct:
        lam += 0.25
    # Poisson-ish without numpy: use geometric sum approximation
    # For demo, cap at 3.
    hints = 0
    while hints < 3 and rng.random() < min(0.85, lam / 2.0):
        hints += 1
        lam *= 0.55
    return hints


def sample_time_taken(profile: StudentProfile, q: Question, hints_used: int, rng: random.Random) -> int:
    params = ScoringParams()
    base = expected_time_seconds(q, params) * profile.speed_multiplier
    # Hints slow you down; add noise
    base *= (1.0 + 0.18 * hints_used)
    noise = rng.uniform(0.80, 1.35)
    t = int(round(base * noise))
    return max(5, min(240, t))


def sample_confidence(profile: StudentProfile, is_correct: bool, hints_used: int, q: Question, rng: random.Random) -> int:
    # Base confidence starts near 3; shift by correctness and profile bias.
    c = 3.0 + profile.confidence_bias
    c += 0.7 if is_correct else -0.8
    c -= 0.35 * hints_used
    c -= 0.25 * q.transfer_load
    c += rng.uniform(-0.6, 0.6)
    return int(max(1, min(5, round(c))))


def choose_questions_for_simulation(conn: sqlite3.Connection) -> List[Question]:
    # Use only topics that currently have questions seeded.
    topics = list_topics(conn)
    out: List[Question] = []
    for t in topics:
        out.extend(list_questions_by_topic(conn, t.id))
    return out


def simulate_student(
    conn: sqlite3.Connection,
    *,
    profile: StudentProfile,
    questions: List[Question],
    n_attempts: int,
    rng: random.Random,
    start_time: datetime,
) -> None:
    # Ensure student exists
    conn.execute(
        """
        INSERT OR REPLACE INTO students (id, display_name, created_at)
        VALUES (?, ?, ?)
        """,
        (profile.profile_id, profile.display_name, start_time.isoformat().replace("+00:00", "Z")),
    )

    # Weighted topic sampling: attempt more in weak areas for some profiles.
    by_topic: Dict[str, List[Question]] = {}
    for q in questions:
        by_topic.setdefault(q.topic_id, []).append(q)

    topic_ids = list(by_topic.keys())
    if not topic_ids:
        raise RuntimeError("No seeded questions found. Run scripts/seed_questions.py first.")

    # For the "strong overall" demo student, concentrate practice on a smaller set of topics
    # so the dashboard shows some clearly Strong topics (mastery climbs with repetition).
    if profile.profile_id == "stu_strong_overall":
        focus = [
            "t_integer_add_sub",
            "t_integer_mult_div",
            "t_decimal_place_value",
            "t_simple_equations_1step",
            "t_compare_order_rational",
        ]
        topic_ids = [t for t in topic_ids if t in focus] or topic_ids

    def topic_weight(tid: str) -> float:
        delta = profile.topic_ability_delta.get(tid, 0.0)
        # If weaker in a topic, sample it more to make weakness visible on dashboard.
        return 1.0 + max(0.0, -delta) * 0.8

    weights = [topic_weight(tid) for tid in topic_ids]

    current_time = start_time
    for _ in range(n_attempts):
        topic_id = rng.choices(topic_ids, weights=weights, k=1)[0]
        q = rng.choice(by_topic[topic_id])

        p_correct = probability_correct(profile, q)
        is_correct = rng.random() < p_correct

        hints_used = sample_hints_used(profile, is_correct, q, rng)
        time_taken = sample_time_taken(profile, q, hints_used, rng)
        conf = sample_confidence(profile, is_correct, hints_used, q, rng)

        # Spread timestamps slightly
        current_time = current_time + timedelta(seconds=rng.randint(15, 120))

        att = Attempt(
            id=f"att_{uuid.uuid4().hex[:12]}",
            student_id=profile.profile_id,
            question_id=q.id,
            topic_id=q.topic_id,
            correctness=is_correct,
            time_taken_seconds=time_taken,
            hints_used=hints_used,
            confidence_rating=conf,
            self_report_reason=None,
            submitted_at=current_time,
        )
        insert_attempt(conn, att)

        prev = get_student_topic_state(conn, student_id=att.student_id, topic_id=att.topic_id)
        upd = update_student_topic_state(prev, attempt=att, question=q)
        upsert_student_topic_state(conn, upd.new)


# ----------------------------
# 3) Seeding script entrypoint
# ----------------------------


def summarize_student(conn: sqlite3.Connection, student_id: str) -> Dict[str, List[Tuple[str, float]]]:
    rows = conn.execute(
        """
        SELECT s.topic_id, s.mastery_score, s.fragility_score, s.fluency_score, s.evidence_count,
               t.title
        FROM student_topic_state s
        LEFT JOIN topics t ON t.id = s.topic_id
        WHERE s.student_id = ?
        """,
        (student_id,),
    ).fetchall()

    enriched = [
        {
            "topic_id": r["topic_id"],
            "title": r["title"] or r["topic_id"],
            "mastery": float(r["mastery_score"]),
            "fragility": float(r["fragility_score"]),
            "fluency": float(r["fluency_score"]),
            "evidence": int(r["evidence_count"]),
        }
        for r in rows
    ]

    weakest = sorted(enriched, key=lambda x: x["mastery"])[:5]
    strongest = sorted(enriched, key=lambda x: x["mastery"], reverse=True)[:5]
    fragile = sorted(enriched, key=lambda x: x["fragility"], reverse=True)[:5]

    def pack(items):
        return [(f"{x['title']} ({x['topic_id']})", round(x["mastery"], 2)) for x in items]

    return {
        "weakest_by_mastery": pack(weakest),
        "strongest_by_mastery": pack(strongest),
        "most_fragile": [(f"{x['title']} ({x['topic_id']})", round(x["fragility"], 2)) for x in fragile],
        "lowest_fluency": [(f"{x['title']} ({x['topic_id']})", round(x["fluency"], 2)) for x in sorted(enriched, key=lambda x: x["fluency"])[:5]],
    }


def main() -> None:
    rng = random.Random(7)  # deterministic demo seed
    conn = connect()
    init_db(conn)

    questions = choose_questions_for_simulation(conn)
    profiles = build_profiles()

    # Clear previous simulation data (demo-only)
    with conn:
        conn.execute("DELETE FROM attempts;")
        conn.execute("DELETE FROM student_topic_state;")
        conn.execute("DELETE FROM students;")

    start = datetime.now(tz=timezone.utc) - timedelta(hours=2)

    with conn:
        for p in profiles:
            # More attempts for clearer dashboards (still small for demo).
            if p.profile_id == "stu_strong_overall":
                n = rng.randint(180, 230)
            else:
                n = rng.randint(90, 140)
            simulate_student(conn, profile=p, questions=questions, n_attempts=n, rng=rng, start_time=start)

    print("OK: simulated students:", len(profiles))
    for p in profiles:
        summary = summarize_student(conn, p.profile_id)
        print("\n==", p.display_name, f"({p.profile_id}) ==")
        print("weakest_by_mastery:", summary["weakest_by_mastery"])
        print("most_fragile:", summary["most_fragile"])
        print("lowest_fluency:", summary["lowest_fluency"])


if __name__ == "__main__":
    main()

