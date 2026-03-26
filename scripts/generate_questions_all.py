from __future__ import annotations

"""
Generate a full demo question bank (~150 items) deterministically.

This is NOT ML. It's a simple content generator to rapidly produce consistent demo questions
across all seeded Grade 7 Math topics.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


GRAPH_PATH = Path("data/grade7_math_graph.json")
OUT_PATH = Path("data/grade7_math_questions_seed_all.json")


def qid(topic_id: str, n: int) -> str:
    return f"q_{topic_id}_{n:03d}"


def mcq(question_text: str, choices: List[str], correct: str) -> Tuple[str, List[str], str]:
    return "mcq", choices, correct


def numeric(question_text: str, correct: str) -> Tuple[str, List[str], str]:
    return "numeric", [], correct


def short_text(question_text: str, correct: str) -> Tuple[str, List[str], str]:
    return "short_text", [], correct


def base_meta(*, difficulty: float, c: float, p: float, t: float, diag: float) -> Dict:
    return {
        "difficulty_prior": float(difficulty),
        "conceptual_load": float(c),
        "procedural_load": float(p),
        "transfer_load": float(t),
        "diagnostic_value": float(diag),
    }


def topic_questions(topic_id: str) -> List[Dict]:
    """
    4 per topic by default:
    - direct_easy
    - direct_medium
    - diagnostic_trap
    - word_problem_transfer
    Some topics get a 5th item (see EXTRA_TOPICS).
    """
    q: List[Dict] = []

    # Foundations
    if topic_id == "t_numline_rational":
        at, ch, ca = mcq("Which number is greatest?", ["-0.5", "-1/4", "0", "1/3"], "1/3")
        q.append({"question_text": "Which number is greatest?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.25, c=0.40, p=0.10, t=0.05, diag=0.55),
                  "hint_text": "Positive numbers are greater than 0; compare fractions/decimals by value.",
                  "explanation_text": "1/3 is positive and greater than 0, so it is the greatest here.",
                  "likely_error_tags": ["negative_ordering_error", "fraction_size_error"]})
        at, ch, ca = short_text("Order from least to greatest: -2, -1.5, 0.2, 0", "-2, -1.5, 0, 0.2")
        q.append({"question_text": "Order from least to greatest: -2, -1.5, 0.2, 0", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.40, c=0.45, p=0.15, t=0.10, diag=0.60),
                  "hint_text": "Negatives are less than 0. Among negatives, farther left is smaller.",
                  "explanation_text": "-2 < -1.5 < 0 < 0.2.",
                  "likely_error_tags": ["negative_decimal_ordering_error"]})
        at, ch, ca = mcq("True or False: -3 is greater than -1.", ["True", "False"], "False")
        q.append({"question_text": "True or False: -3 is greater than -1.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.30, c=0.35, p=0.05, t=0.05, diag=0.55),
                  "hint_text": "On the number line, numbers to the right are greater.",
                  "explanation_text": "-3 is left of -1, so it is smaller.",
                  "likely_error_tags": ["negative_ordering_error"]})
        at, ch, ca = numeric("A point is at -4. What is its distance from 3?", "7")
        q.append({"question_text": "A point is at -4. What is its distance from 3?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.50, c=0.45, p=0.20, t=0.15, diag=0.60),
                  "hint_text": "Distance = absolute difference: |3 - (-4)|.",
                  "explanation_text": "3 - (-4) = 7, so the distance is 7.",
                  "likely_error_tags": ["subtracting_negative_error", "distance_formula_error"]})
        return q

    if topic_id == "t_compare_order_rational":
        at, ch, ca = mcq("Which is greater?", ["0.7", "0.65"], "0.7")
        q.append({"question_text": "Which is greater?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.30, c=0.35, p=0.15, t=0.05, diag=0.45),
                  "hint_text": "Write 0.7 as 0.70.",
                  "explanation_text": "0.70 > 0.65, so 0.7 is greater.",
                  "likely_error_tags": ["place_value_error"]})
        at, ch, ca = mcq("Which fraction is larger?", ["3/8", "1/2"], "1/2")
        q.append({"question_text": "Which fraction is larger?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.45, p=0.25, t=0.10, diag=0.60),
                  "hint_text": "1/2 = 4/8.",
                  "explanation_text": "3/8 vs 4/8 → 1/2 is larger.",
                  "likely_error_tags": ["numerator_only_comparison"]})
        at, ch, ca = short_text("Order from least to greatest: -2, -2.5, -1.9", "-2.5, -2, -1.9")
        q.append({"question_text": "Order from least to greatest: -2, -2.5, -1.9", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.45, p=0.20, t=0.10, diag=0.65),
                  "hint_text": "For negatives, bigger absolute value means smaller number.",
                  "explanation_text": "-2.5 < -2 < -1.9.",
                  "likely_error_tags": ["negative_decimal_ordering_error"]})
        at, ch, ca = mcq("Which is closest to 1?", ["0.98", "1.02", "0.89"], "0.98")
        q.append({"question_text": "Which is closest to 1?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.40, c=0.40, p=0.15, t=0.10, diag=0.45),
                  "hint_text": "Compare distances from 1.",
                  "explanation_text": "0.98 is 0.02 away from 1 (same as 1.02), and closer than 0.89.",
                  "likely_error_tags": ["distance_to_one_error"]})
        return q

    if topic_id == "t_round_estimate":
        at, ch, ca = numeric("Round 6.48 to the nearest tenth.", "6.5")
        q.append({"question_text": "Round 6.48 to the nearest tenth.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.25, c=0.30, p=0.20, t=0.05, diag=0.35),
                  "hint_text": "Look at the hundredths digit.",
                  "explanation_text": "Hundredths digit is 8, so 6.4 rounds up to 6.5.",
                  "likely_error_tags": ["rounding_rule_error"]})
        at, ch, ca = numeric("Estimate 49 × 21 by rounding to the nearest tens.", "1000")
        q.append({"question_text": "Estimate 49 × 21 by rounding to the nearest tens.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.35, p=0.35, t=0.15, diag=0.45),
                  "hint_text": "49≈50 and 21≈20.",
                  "explanation_text": "50×20 = 1000.",
                  "likely_error_tags": ["rounding_error", "estimate_strategy_missing"]})
        at, ch, ca = mcq("An exact answer is 198. Which estimate is most reasonable?", ["20", "200", "2000", "20000"], "200")
        q.append({"question_text": "An exact answer is 198. Which estimate is most reasonable?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.35, p=0.15, t=0.10, diag=0.50),
                  "hint_text": "198 is close to 200.",
                  "explanation_text": "198 rounds to about 200.",
                  "likely_error_tags": ["magnitude_error"]})
        at, ch, ca = short_text("Explain briefly why estimation is useful when checking answers.", "It helps check reasonableness")
        q.append({"question_text": "Explain briefly why estimation is useful when checking answers.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.55, p=0.10, t=0.20, diag=0.50),
                  "hint_text": "Think: does the answer size make sense?",
                  "explanation_text": "Estimates help you see if an exact answer is too big or too small.",
                  "likely_error_tags": ["metacognition_gap"]})
        return q

    # Integers
    if topic_id == "t_integer_abs_value":
        at, ch, ca = numeric("What is |−9| ?", "9")
        q.append({"question_text": "What is |−9| ?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.20, c=0.30, p=0.05, t=0.05, diag=0.40),
                  "hint_text": "Absolute value is distance from 0.",
                  "explanation_text": "Distance from 0 to −9 is 9.",
                  "likely_error_tags": ["absolute_value_sign_error"]})
        at, ch, ca = numeric("Find the distance between −2 and 5.", "7")
        q.append({"question_text": "Find the distance between −2 and 5.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.45, p=0.20, t=0.10, diag=0.60),
                  "hint_text": "Distance = |5 − (−2)|.",
                  "explanation_text": "5 − (−2)=7 so the distance is 7.",
                  "likely_error_tags": ["subtracting_negative_error"]})
        at, ch, ca = mcq("Which is greater?", ["|−4|", "|3|", "Equal"], "|−4|")
        q.append({"question_text": "Which is greater?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.40, p=0.10, t=0.05, diag=0.55),
                  "hint_text": "Compute both absolute values.",
                  "explanation_text": "|−4|=4, |3|=3 so |−4| is greater.",
                  "likely_error_tags": ["absolute_value_confusion"]})
        at, ch, ca = numeric("A submarine is at −120 m and rises 35 m. New position?", "-85")
        q.append({"question_text": "A submarine is at −120 m and rises 35 m. New position?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.45, p=0.25, t=0.25, diag=0.65),
                  "hint_text": "Rising means add 35.",
                  "explanation_text": "−120 + 35 = −85.",
                  "likely_error_tags": ["context_direction_error"]})
        return q

    if topic_id == "t_integer_add_sub":
        at, ch, ca = numeric("Compute: −7 + 12", "5")
        q.append({"question_text": "Compute: −7 + 12", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.35, p=0.25, t=0.10, diag=0.55),
                  "hint_text": "12 − 7 = 5.",
                  "explanation_text": "−7 + 12 = 5.",
                  "likely_error_tags": ["sign_error"]})
        at, ch, ca = numeric("Compute: 6 − (−3)", "9")
        q.append({"question_text": "Compute: 6 − (−3)", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.45, p=0.25, t=0.10, diag=0.70),
                  "hint_text": "Subtracting a negative is adding.",
                  "explanation_text": "6 − (−3)=6+3=9.",
                  "likely_error_tags": ["subtracting_negative_error"]})
        at, ch, ca = mcq("Which is correct?", ["−9 − 4 = −5", "−9 − 4 = −13", "−9 − 4 = 13", "−9 − 4 = 5"], "−9 − 4 = −13")
        q.append({"question_text": "Which is correct?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.40, c=0.35, p=0.30, t=0.10, diag=0.65),
                  "hint_text": "Subtracting makes the number smaller (more negative).",
                  "explanation_text": "−9 − 4 = −13.",
                  "likely_error_tags": ["subtract_sign_error"]})
        at, ch, ca = numeric("Temperature was −2°C and rose 7°C. New temperature?", "5")
        q.append({"question_text": "Temperature was −2°C and rose 7°C. New temperature?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.50, c=0.40, p=0.25, t=0.30, diag=0.60),
                  "hint_text": "Compute −2 + 7.",
                  "explanation_text": "−2 + 7 = 5°C.",
                  "likely_error_tags": ["context_direction_error"]})
        return q

    if topic_id == "t_integer_mult_div":
        at, ch, ca = numeric("Compute: (−4) × 6", "-24")
        q.append({"question_text": "Compute: (−4) × 6", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.25, p=0.35, t=0.10, diag=0.50),
                  "hint_text": "Negative × positive = negative.",
                  "explanation_text": "4×6=24, so result is −24.",
                  "likely_error_tags": ["sign_rule_error"]})
        at, ch, ca = numeric("Compute: (−3) × (−5)", "15")
        q.append({"question_text": "Compute: (−3) × (−5)", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.40, c=0.30, p=0.35, t=0.10, diag=0.60),
                  "hint_text": "Negative × negative = positive.",
                  "explanation_text": "3×5=15 and sign is positive.",
                  "likely_error_tags": ["sign_rule_error"]})
        at, ch, ca = numeric("Compute: 28 ÷ (−7)", "-4")
        q.append({"question_text": "Compute: 28 ÷ (−7)", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.25, p=0.35, t=0.10, diag=0.55),
                  "hint_text": "Positive ÷ negative = negative.",
                  "explanation_text": "28 ÷ 7 = 4, so −4.",
                  "likely_error_tags": ["sign_rule_error"]})
        at, ch, ca = numeric("A diver goes down 5 m each minute for 6 minutes. Change in position?", "-30")
        q.append({"question_text": "A diver goes down 5 m each minute for 6 minutes. Change in position?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.40, p=0.30, t=0.35, diag=0.65),
                  "hint_text": "Down is negative. Compute (−5)×6.",
                  "explanation_text": "(−5)×6 = −30.",
                  "likely_error_tags": ["context_sign_error"]})
        return q

    if topic_id == "t_integer_expressions":
        at, ch, ca = numeric("Evaluate: 3 + 2×(−4)", "-5")
        q.append({"question_text": "Evaluate: 3 + 2×(−4)", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.35, p=0.45, t=0.10, diag=0.60),
                  "hint_text": "Multiply first: 2×(−4)=−8, then add 3.",
                  "explanation_text": "3 + (−8) = −5.",
                  "likely_error_tags": ["order_of_operations_error", "sign_error"]})
        at, ch, ca = numeric("Evaluate: −6 − (−2) + 5", "1")
        q.append({"question_text": "Evaluate: −6 − (−2) + 5", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.35, p=0.45, t=0.10, diag=0.65),
                  "hint_text": "Subtracting a negative is adding.",
                  "explanation_text": "−6 + 2 + 5 = 1.",
                  "likely_error_tags": ["subtracting_negative_error"]})
        at, ch, ca = mcq("Which is the value of x if x = −3?", ["x+5", "5−x", "x−5", "−x+5"], "x+5")
        q.append({"question_text": "If x = −3, which expression equals 2?", "answer_type": "mcq",
                  "choices": ["x+5", "5−x", "x−5", "−x+5"], "correct_answer": "x+5",
                  **base_meta(difficulty=0.60, c=0.40, p=0.45, t=0.10, diag=0.70),
                  "hint_text": "Plug in x = −3 and compute each.",
                  "explanation_text": "x+5 = −3+5 = 2. Others are not 2.",
                  "likely_error_tags": ["substitution_error"]})
        at, ch, ca = short_text("Explain why 2×(−4) is negative.", "Because a positive times a negative is negative")
        q.append({"question_text": "Explain why 2×(−4) is negative.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.55, p=0.15, t=0.10, diag=0.50),
                  "hint_text": "Think about sign rules.",
                  "explanation_text": "A positive times a negative gives a negative product.",
                  "likely_error_tags": ["sign_rule_misconception"]})
        return q

    # Fractions
    if topic_id == "t_fraction_concepts":
        at, ch, ca = mcq("Which fraction is equivalent to 2/3?", ["4/6", "2/5", "3/2", "6/4"], "4/6")
        q.append({"question_text": "Which fraction is equivalent to 2/3?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.45, p=0.20, t=0.05, diag=0.60),
                  "hint_text": "Multiply top and bottom by the same number.",
                  "explanation_text": "2/3×(2/2)=4/6.",
                  "likely_error_tags": ["equivalence_error"]})
        at, ch, ca = numeric("A pizza is cut into 8 equal slices. You eat 3 slices. What fraction did you eat?", "3/8")
        q.append({"question_text": "A pizza is cut into 8 equal slices. You eat 3 slices. What fraction did you eat?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.25, c=0.40, p=0.10, t=0.25, diag=0.45),
                  "hint_text": "Parts eaten / total parts.",
                  "explanation_text": "3 out of 8 → 3/8.",
                  "likely_error_tags": ["part_whole_reversal"]})
        at, ch, ca = mcq("True or False: 3/5 is the same as 3 ÷ 5.", ["True", "False"], "True")
        q.append({"question_text": "True or False: 3/5 is the same as 3 ÷ 5.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.40, c=0.55, p=0.10, t=0.10, diag=0.65),
                  "hint_text": "A fraction bar means division.",
                  "explanation_text": "3/5 represents 3 divided by 5.",
                  "likely_error_tags": ["fraction_as_division_misconception"]})
        at, ch, ca = mcq("Which is closer to 1?", ["5/6", "3/4"], "5/6")
        q.append({"question_text": "Which is closer to 1?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.50, c=0.55, p=0.25, t=0.10, diag=0.55),
                  "hint_text": "Compare 1−fraction.",
                  "explanation_text": "1−5/6=1/6 and 1−3/4=1/4; 1/6 is smaller so 5/6 is closer.",
                  "likely_error_tags": ["fraction_distance_to_one_error"]})
        return q

    if topic_id == "t_simplify_fractions":
        at, ch, ca = short_text("Simplify: 12/18", "2/3")
        q.append({"question_text": "Simplify: 12/18", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.35, p=0.40, t=0.05, diag=0.55),
                  "hint_text": "Divide by the GCF (6).",
                  "explanation_text": "12/18 = 2/3.",
                  "likely_error_tags": ["gcf_error"]})
        at, ch, ca = short_text("Simplify: 15/20", "3/4")
        q.append({"question_text": "Simplify: 15/20", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.40, c=0.30, p=0.35, t=0.05, diag=0.45),
                  "hint_text": "Divide by 5.",
                  "explanation_text": "15/20 = 3/4.",
                  "likely_error_tags": ["simplify_error"]})
        at, ch, ca = mcq("Which fraction is already simplest?", ["6/9", "8/12", "7/10", "12/16"], "7/10")
        q.append({"question_text": "Which fraction is already simplest?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.40, p=0.25, t=0.05, diag=0.60),
                  "hint_text": "Check common factors.",
                  "explanation_text": "7 and 10 share no factor >1.",
                  "likely_error_tags": ["gcf_error"]})
        at, ch, ca = short_text("Simplify: 9/27", "1/3")
        q.append({"question_text": "Simplify: 9/27", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.25, p=0.30, t=0.05, diag=0.45),
                  "hint_text": "Divide by 9.",
                  "explanation_text": "9/27 = 1/3.",
                  "likely_error_tags": ["division_error"]})
        return q

    if topic_id == "t_compare_fractions":
        at, ch, ca = mcq("Which is larger?", ["2/5", "3/5"], "3/5")
        q.append({"question_text": "Which is larger?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.30, c=0.35, p=0.15, t=0.05, diag=0.40),
                  "hint_text": "Same denominator, compare numerators.",
                  "explanation_text": "3/5 > 2/5.",
                  "likely_error_tags": ["numerator_comparison_error"]})
        at, ch, ca = mcq("Which is larger?", ["3/8", "1/2"], "1/2")
        q.append({"question_text": "Which is larger?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.45, p=0.25, t=0.10, diag=0.60),
                  "hint_text": "Convert 1/2 to 4/8.",
                  "explanation_text": "4/8 > 3/8.",
                  "likely_error_tags": ["common_denominator_error"]})
        at, ch, ca = mcq("Which is larger?", ["5/6", "7/9"], "5/6")
        q.append({"question_text": "Which is larger?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.50, p=0.35, t=0.10, diag=0.65),
                  "hint_text": "Compare to 1: 5/6 is 1/6 away; 7/9 is 2/9 away.",
                  "explanation_text": "1/6 ≈ 0.167 and 2/9 ≈ 0.222, so 5/6 is closer to 1 and larger.",
                  "likely_error_tags": ["benchmark_fraction_error"]})
        at, ch, ca = short_text("Order from least to greatest: 1/2, 2/3, 3/4", "1/2, 2/3, 3/4")
        q.append({"question_text": "Order from least to greatest: 1/2, 2/3, 3/4", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.45, p=0.30, t=0.10, diag=0.55),
                  "hint_text": "Use common denominators or decimals.",
                  "explanation_text": "0.5 < 0.666... < 0.75.",
                  "likely_error_tags": ["fraction_ordering_error"]})
        return q

    if topic_id == "t_fraction_add_sub_like":
        at, ch, ca = short_text("Compute: 3/8 + 2/8", "5/8")
        q.append({"question_text": "Compute: 3/8 + 2/8", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.30, p=0.35, t=0.05, diag=0.45),
                  "hint_text": "Add numerators; keep denominator.",
                  "explanation_text": "3/8+2/8=5/8.",
                  "likely_error_tags": ["add_denominator_error"]})
        at, ch, ca = short_text("Compute: 7/10 − 3/10", "4/10")
        q.append({"question_text": "Compute: 7/10 − 3/10", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.30, p=0.35, t=0.05, diag=0.45),
                  "hint_text": "Subtract numerators; keep denominator.",
                  "explanation_text": "7/10−3/10=4/10 (simplify to 2/5 if asked).",
                  "likely_error_tags": ["subtract_denominator_error"]})
        at, ch, ca = mcq("Which is correct?", ["1/5+2/5=3/10", "1/5+2/5=3/5", "1/5+2/5=2/5", "1/5+2/5=1/10"], "1/5+2/5=3/5")
        q.append({"question_text": "Which is correct?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.35, p=0.35, t=0.05, diag=0.65),
                  "hint_text": "Denominators stay the same for like denominators.",
                  "explanation_text": "1/5+2/5=3/5.",
                  "likely_error_tags": ["add_denominators_error"]})
        at, ch, ca = numeric("You drank 2/6 liter of water and then 1/6 liter. Total?", "3/6")
        q.append({"question_text": "You drank 2/6 liter of water and then 1/6 liter. Total?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.40, p=0.35, t=0.20, diag=0.55),
                  "hint_text": "Add: 2/6 + 1/6.",
                  "explanation_text": "3/6 (which equals 1/2).",
                  "likely_error_tags": ["word_problem_translation_error"]})
        return q

    if topic_id == "t_fraction_add_sub_unlike":
        at, ch, ca = short_text("Compute: 1/4 + 1/6", "5/12")
        q.append({"question_text": "Compute: 1/4 + 1/6", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.45, p=0.55, t=0.10, diag=0.70),
                  "hint_text": "Use denominator 12.",
                  "explanation_text": "3/12+2/12=5/12.",
                  "likely_error_tags": ["common_denominator_error"]})
        at, ch, ca = short_text("Compute: 3/5 − 1/2", "1/10")
        q.append({"question_text": "Compute: 3/5 − 1/2", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.50, p=0.60, t=0.15, diag=0.70),
                  "hint_text": "Use denominator 10.",
                  "explanation_text": "6/10−5/10=1/10.",
                  "likely_error_tags": ["common_denominator_error"]})
        at, ch, ca = mcq("2/3 + 1/6 equals:", ["3/9", "3/6", "5/6", "1/2"], "5/6")
        q.append({"question_text": "2/3 + 1/6 equals:", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.45, p=0.55, t=0.10, diag=0.75),
                  "hint_text": "2/3=4/6.",
                  "explanation_text": "4/6+1/6=5/6.",
                  "likely_error_tags": ["add_denominators_error"]})
        at, ch, ca = short_text("A recipe needs 3/4 cup milk. You have 1/3 cup. How much more do you need?", "5/12")
        q.append({"question_text": "A recipe needs 3/4 cup milk. You have 1/3 cup. How much more do you need?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.70, c=0.55, p=0.60, t=0.35, diag=0.70),
                  "hint_text": "Compute 3/4−1/3.",
                  "explanation_text": "9/12−4/12=5/12.",
                  "likely_error_tags": ["word_problem_translation_error"]})
        return q

    if topic_id == "t_fraction_mult":
        at, ch, ca = short_text("Compute: 2/3 × 3/4", "1/2")
        q.append({"question_text": "Compute: 2/3 × 3/4", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.40, p=0.55, t=0.10, diag=0.60),
                  "hint_text": "Multiply numerators and denominators, then simplify.",
                  "explanation_text": "6/12 = 1/2.",
                  "likely_error_tags": ["multiply_denominators_missing", "simplify_error"]})
        at, ch, ca = numeric("Compute: 1/2 × 8", "4")
        q.append({"question_text": "Compute: 1/2 × 8", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.35, p=0.35, t=0.15, diag=0.45),
                  "hint_text": "Half of 8 is 4.",
                  "explanation_text": "1/2 of 8 is 4.",
                  "likely_error_tags": ["fraction_of_quantity_error"]})
        at, ch, ca = mcq("Which is bigger?", ["3/4 of 12", "2/3 of 12"], "3/4 of 12")
        q.append({"question_text": "Which is bigger?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.45, p=0.35, t=0.25, diag=0.55),
                  "hint_text": "Compute both: 3/4 of 12 is 9; 2/3 of 12 is 8.",
                  "explanation_text": "9 is greater than 8.",
                  "likely_error_tags": ["compare_fraction_of_quantity_error"]})
        at, ch, ca = short_text("A ribbon is 6 m long. You use 2/3 of it. How many meters is that?", "4")
        q.append({"question_text": "A ribbon is 6 m long. You use 2/3 of it. How many meters is that?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.40, p=0.45, t=0.30, diag=0.60),
                  "hint_text": "Compute 2/3 × 6.",
                  "explanation_text": "2/3 × 6 = 4.",
                  "likely_error_tags": ["word_problem_translation_error"]})
        return q

    if topic_id == "t_fraction_div":
        at, ch, ca = short_text("Compute: 1/2 ÷ 1/4", "2")
        q.append({"question_text": "Compute: 1/2 ÷ 1/4", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.70, c=0.50, p=0.65, t=0.10, diag=0.70),
                  "hint_text": "Multiply by the reciprocal: 1/2 × 4/1.",
                  "explanation_text": "1/2 × 4 = 2.",
                  "likely_error_tags": ["invert_multiply_error"]})
        at, ch, ca = short_text("Compute: 3/4 ÷ 3", "1/4")
        q.append({"question_text": "Compute: 3/4 ÷ 3", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.60, t=0.10, diag=0.60),
                  "hint_text": "Dividing by 3 is multiplying by 1/3.",
                  "explanation_text": "3/4 × 1/3 = 1/4.",
                  "likely_error_tags": ["divide_by_integer_error"]})
        at, ch, ca = mcq("How many 1/3-cup servings are in 1 cup?", ["1", "2", "3", "4"], "3")
        q.append({"question_text": "How many 1/3-cup servings are in 1 cup?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.55, p=0.45, t=0.35, diag=0.75),
                  "hint_text": "Compute 1 ÷ (1/3).",
                  "explanation_text": "1 ÷ (1/3) = 3.",
                  "likely_error_tags": ["division_as_groups_misconception"]})
        at, ch, ca = short_text("Compute: 2/5 ÷ 1/10", "4")
        q.append({"question_text": "Compute: 2/5 ÷ 1/10", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.75, c=0.50, p=0.70, t=0.10, diag=0.70),
                  "hint_text": "2/5 × 10/1.",
                  "explanation_text": "2/5 × 10 = 20/5 = 4.",
                  "likely_error_tags": ["invert_multiply_error", "simplify_error"]})
        return q

    # Decimals
    if topic_id == "t_decimal_place_value":
        at, ch, ca = numeric("Which digit is in the hundredths place in 4.372?", "7")
        q.append({"question_text": "Which digit is in the hundredths place in 4.372?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.30, c=0.35, p=0.15, t=0.05, diag=0.45),
                  "hint_text": "Hundredths is the second digit right of the decimal.",
                  "explanation_text": "4.372 has 7 in the hundredths place.",
                  "likely_error_tags": ["place_value_error"]})
        at, ch, ca = mcq("Which is greater?", ["0.503", "0.53"], "0.53")
        q.append({"question_text": "Which is greater?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.40, c=0.40, p=0.20, t=0.05, diag=0.55),
                  "hint_text": "Write 0.53 as 0.530.",
                  "explanation_text": "0.530 > 0.503.",
                  "likely_error_tags": ["decimal_length_misconception"]})
        at, ch, ca = short_text("Write 0.09 as a fraction in simplest form.", "9/100")
        q.append({"question_text": "Write 0.09 as a fraction in simplest form.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.50, c=0.45, p=0.30, t=0.10, diag=0.60),
                  "hint_text": "0.09 is 9 hundredths.",
                  "explanation_text": "9/100.",
                  "likely_error_tags": ["fraction_from_decimal_error"]})
        at, ch, ca = numeric("A bottle holds 1.5 liters. How many milliliters is that? (1 L = 1000 mL)", "1500")
        q.append({"question_text": "A bottle holds 1.5 liters. How many milliliters is that? (1 L = 1000 mL)", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.40, p=0.40, t=0.40, diag=0.60),
                  "hint_text": "Multiply by 1000.",
                  "explanation_text": "1.5×1000=1500.",
                  "likely_error_tags": ["unit_conversion_error"]})
        return q

    if topic_id == "t_decimal_add_sub":
        at, ch, ca = numeric("Compute: 3.4 + 2.56", "5.96")
        q.append({"question_text": "Compute: 3.4 + 2.56", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.30, p=0.45, t=0.10, diag=0.50),
                  "hint_text": "Align decimals: 3.40 + 2.56.",
                  "explanation_text": "3.40 + 2.56 = 5.96.",
                  "likely_error_tags": ["decimal_alignment_error"]})
        at, ch, ca = numeric("Compute: 10.00 − 3.75", "6.25")
        q.append({"question_text": "Compute: 10.00 − 3.75", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.50, c=0.30, p=0.50, t=0.10, diag=0.55),
                  "hint_text": "Borrow across the decimal if needed.",
                  "explanation_text": "10.00 − 3.75 = 6.25.",
                  "likely_error_tags": ["borrowing_error"]})
        at, ch, ca = mcq("Which is correct?", ["2.3 + 0.7 = 2.10", "2.3 + 0.7 = 3.0", "2.3 + 0.7 = 2.37", "2.3 + 0.7 = 23.7"], "2.3 + 0.7 = 3.0")
        q.append({"question_text": "Which is correct?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.40, c=0.30, p=0.35, t=0.05, diag=0.60),
                  "hint_text": "2.3 is 23 tenths and 0.7 is 7 tenths.",
                  "explanation_text": "23 tenths + 7 tenths = 30 tenths = 3.0.",
                  "likely_error_tags": ["place_value_error"]})
        at, ch, ca = numeric("You buy snacks costing $2.35 and $1.70. Total cost?", "4.05")
        q.append({"question_text": "You buy snacks costing $2.35 and $1.70. Total cost?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.30, p=0.45, t=0.30, diag=0.55),
                  "hint_text": "Add as decimals: 2.35+1.70.",
                  "explanation_text": "4.05.",
                  "likely_error_tags": ["decimal_addition_error"]})
        return q

    if topic_id == "t_decimal_mult":
        at, ch, ca = numeric("Compute: 0.6 × 0.3", "0.18")
        q.append({"question_text": "Compute: 0.6 × 0.3", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.35, p=0.55, t=0.10, diag=0.55),
                  "hint_text": "6×3=18 and there are 2 decimal places total.",
                  "explanation_text": "0.18.",
                  "likely_error_tags": ["decimal_place_error"]})
        at, ch, ca = numeric("Compute: 2.5 × 4", "10")
        q.append({"question_text": "Compute: 2.5 × 4", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.50, c=0.30, p=0.45, t=0.10, diag=0.45),
                  "hint_text": "25×4=100 then divide by 10.",
                  "explanation_text": "10.",
                  "likely_error_tags": ["decimal_multiplication_error"]})
        at, ch, ca = mcq("Which is correct?", ["0.2×0.5=1.0", "0.2×0.5=0.1", "0.2×0.5=0.7", "0.2×0.5=0.01"], "0.2×0.5=0.1")
        q.append({"question_text": "Which is correct?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.35, p=0.55, t=0.10, diag=0.65),
                  "hint_text": "2×5=10; two decimal places total.",
                  "explanation_text": "0.1.",
                  "likely_error_tags": ["decimal_place_error"]})
        at, ch, ca = numeric("A notebook costs $1.25. What is the cost of 6 notebooks?", "7.5")
        q.append({"question_text": "A notebook costs $1.25. What is the cost of 6 notebooks?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.35, p=0.60, t=0.35, diag=0.60),
                  "hint_text": "Compute 1.25×6.",
                  "explanation_text": "1.25×6=7.50.",
                  "likely_error_tags": ["word_problem_translation_error", "decimal_multiplication_error"]})
        return q

    if topic_id == "t_decimal_div":
        at, ch, ca = short_text("Compute: 4.8 ÷ 2", "2.4")
        q.append({"question_text": "Compute: 4.8 ÷ 2", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.30, p=0.60, t=0.10, diag=0.55),
                  "hint_text": "Divide 48 by 2 then place decimal.",
                  "explanation_text": "2.4.",
                  "likely_error_tags": ["decimal_division_error"]})
        at, ch, ca = short_text("Compute: 3.6 ÷ 0.9", "4")
        q.append({"question_text": "Compute: 3.6 ÷ 0.9", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.75, c=0.40, p=0.70, t=0.15, diag=0.70),
                  "hint_text": "Multiply both by 10: 36 ÷ 9.",
                  "explanation_text": "36/9 = 4.",
                  "likely_error_tags": ["move_decimal_wrong_way"]})
        at, ch, ca = mcq("Which is correct?", ["5 ÷ 0.5 = 2.5", "5 ÷ 0.5 = 10", "5 ÷ 0.5 = 0.1", "5 ÷ 0.5 = 5.5"], "5 ÷ 0.5 = 10")
        q.append({"question_text": "Which is correct?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.70, c=0.45, p=0.65, t=0.10, diag=0.70),
                  "hint_text": "Dividing by 0.5 doubles.",
                  "explanation_text": "5 ÷ 0.5 = 10.",
                  "likely_error_tags": ["division_by_decimal_misconception"]})
        at, ch, ca = short_text("A 7.2 m rope is cut into pieces of length 0.6 m. How many pieces?", "12")
        q.append({"question_text": "A 7.2 m rope is cut into pieces of length 0.6 m. How many pieces?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.75, c=0.45, p=0.70, t=0.35, diag=0.70),
                  "hint_text": "Compute 7.2 ÷ 0.6; multiply both by 10.",
                  "explanation_text": "72 ÷ 6 = 12.",
                  "likely_error_tags": ["word_problem_translation_error"]})
        return q

    # Conversions / Percent / Ratios / Algebra / Geometry
    # For remaining topics, generate simple believable questions via cluster defaults.
    # This keeps demo scope complete without heavy content authoring.

    if topic_id == "t_fraction_decimal_convert":
        at, ch, ca = short_text("Convert 1/4 to a decimal.", "0.25")
        q.append({"question_text": "Convert 1/4 to a decimal.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.45, p=0.35, t=0.10, diag=0.55),
                  "hint_text": "1 ÷ 4 = 0.25.",
                  "explanation_text": "0.25.",
                  "likely_error_tags": ["fraction_to_decimal_error"]})
        at, ch, ca = short_text("Convert 0.6 to a fraction in simplest form.", "3/5")
        q.append({"question_text": "Convert 0.6 to a fraction in simplest form.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.45, p=0.40, t=0.10, diag=0.60),
                  "hint_text": "0.6 = 6/10; simplify.",
                  "explanation_text": "6/10 = 3/5.",
                  "likely_error_tags": ["simplify_error"]})
        at, ch, ca = mcq("Which equals 0.125?", ["1/8", "1/4", "1/2", "1/16"], "1/8")
        q.append({"question_text": "Which equals 0.125?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.45, t=0.10, diag=0.65),
                  "hint_text": "0.125 = 125/1000; simplify.",
                  "explanation_text": "125/1000 = 1/8.",
                  "likely_error_tags": ["decimal_to_fraction_error"]})
        at, ch, ca = short_text("A cup is 0.75 liters. Write 0.75 as a fraction.", "3/4")
        q.append({"question_text": "A cup is 0.75 liters. Write 0.75 as a fraction.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.40, t=0.25, diag=0.60),
                  "hint_text": "0.75 = 75/100; simplify.",
                  "explanation_text": "75/100 = 3/4.",
                  "likely_error_tags": ["simplify_error"]})
        return q

    if topic_id == "t_percent_concepts":
        at, ch, ca = numeric("What percent is the same as 25/100?", "25")
        q.append({"question_text": "What percent is the same as 25/100?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.25, c=0.35, p=0.10, t=0.05, diag=0.40),
                  "hint_text": "Percent means out of 100.",
                  "explanation_text": "25%.",
                  "likely_error_tags": ["percent_definition_error"]})
        at, ch, ca = mcq("Which best describes 60%?", ["60 out of 10", "6 out of 10", "60 out of 100", "0.6 out of 100"], "60 out of 100")
        q.append({"question_text": "Which best describes 60%?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.45, p=0.10, t=0.05, diag=0.55),
                  "hint_text": "Percent means per 100.",
                  "explanation_text": "60% = 60 out of 100.",
                  "likely_error_tags": ["percent_definition_error"]})
        at, ch, ca = mcq("True or False: 150% means more than the whole.", ["True", "False"], "True")
        q.append({"question_text": "True or False: 150% means more than the whole.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.55, p=0.05, t=0.10, diag=0.65),
                  "hint_text": "100% is the whole.",
                  "explanation_text": "150% is 50% more than the whole.",
                  "likely_error_tags": ["percent_over_100_misconception"]})
        at, ch, ca = numeric("Shade 30% of a 10×10 grid. How many squares?", "30")
        q.append({"question_text": "Shade 30% of a 10×10 grid. How many squares?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.55, p=0.15, t=0.15, diag=0.60),
                  "hint_text": "A 10×10 grid has 100 squares.",
                  "explanation_text": "30% of 100 is 30.",
                  "likely_error_tags": ["percent_of_100_error"]})
        return q

    if topic_id == "t_percent_convert":
        at, ch, ca = short_text("Convert 0.25 to a percent.", "25%")
        q.append({"question_text": "Convert 0.25 to a percent.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.40, p=0.40, t=0.10, diag=0.55),
                  "hint_text": "Multiply by 100.",
                  "explanation_text": "0.25×100=25%.",
                  "likely_error_tags": ["percent_conversion_error"]})
        at, ch, ca = short_text("Convert 40% to a decimal.", "0.4")
        q.append({"question_text": "Convert 40% to a decimal.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.35, p=0.35, t=0.05, diag=0.45),
                  "hint_text": "Divide by 100.",
                  "explanation_text": "40% = 0.40 = 0.4.",
                  "likely_error_tags": ["percent_conversion_error"]})
        at, ch, ca = short_text("Convert 3/5 to a percent.", "60%")
        q.append({"question_text": "Convert 3/5 to a percent.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.45, t=0.10, diag=0.65),
                  "hint_text": "3/5 = 0.6 then convert to percent.",
                  "explanation_text": "0.6 = 60%.",
                  "likely_error_tags": ["fraction_to_percent_error"]})
        at, ch, ca = mcq("Which equals 12.5%?", ["0.125", "0.0125", "1.25", "125"], "0.125")
        q.append({"question_text": "Which equals 12.5%?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.40, t=0.10, diag=0.65),
                  "hint_text": "12.5% = 12.5/100.",
                  "explanation_text": "12.5/100 = 0.125.",
                  "likely_error_tags": ["decimal_shift_error"]})
        return q

    if topic_id == "t_percent_of_quantity":
        at, ch, ca = numeric("Find 20% of 50.", "10")
        q.append({"question_text": "Find 20% of 50.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.40, p=0.35, t=0.10, diag=0.50),
                  "hint_text": "20% = 0.2; multiply.",
                  "explanation_text": "0.2×50=10.",
                  "likely_error_tags": ["percent_of_quantity_error"]})
        at, ch, ca = numeric("A shirt costs $40. It is on sale for 25% off. What is the discount amount?", "10")
        q.append({"question_text": "A shirt costs $40. It is on sale for 25% off. What is the discount amount?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.45, p=0.45, t=0.55, diag=0.65),
                  "hint_text": "Discount is 25% of 40.",
                  "explanation_text": "0.25×40=10.",
                  "likely_error_tags": ["sale_price_vs_discount_confusion"]})
        at, ch, ca = numeric("A test has 80 questions. You got 75% correct. How many correct?", "60")
        q.append({"question_text": "A test has 80 questions. You got 75% correct. How many correct?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.45, t=0.55, diag=0.65),
                  "hint_text": "75% = 3/4; take 3/4 of 80.",
                  "explanation_text": "3/4 of 80 is 60.",
                  "likely_error_tags": ["percent_to_fraction_strategy_missing"]})
        at, ch, ca = numeric("A phone costs $200 and sales tax is 8%. What is the tax amount?", "16")
        q.append({"question_text": "A phone costs $200 and sales tax is 8%. What is the tax amount?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.70, c=0.45, p=0.45, t=0.60, diag=0.70),
                  "hint_text": "Compute 0.08×200.",
                  "explanation_text": "16.",
                  "likely_error_tags": ["decimal_shift_error"]})
        return q

    if topic_id == "t_percent_change":
        at, ch, ca = numeric("A price increases from $50 to $60. What is the percent increase?", "20%")
        q.append({"question_text": "A price increases from $50 to $60. What is the percent increase?", "answer_type": "short_text", "choices": [], "correct_answer": "20%",
                  **base_meta(difficulty=0.70, c=0.50, p=0.55, t=0.55, diag=0.65),
                  "hint_text": "Increase is 10. Divide by original 50.",
                  "explanation_text": "10/50 = 0.2 = 20%.",
                  "likely_error_tags": ["wrong_base_for_percent_change"]})
        at, ch, ca = short_text("A score drops from 80 to 60. What percent decrease is that?", "25%")
        q.append({"question_text": "A score drops from 80 to 60. What percent decrease is that?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.75, c=0.50, p=0.60, t=0.55, diag=0.70),
                  "hint_text": "Decrease is 20. Divide by original 80.",
                  "explanation_text": "20/80=0.25=25%.",
                  "likely_error_tags": ["wrong_base_for_percent_change"]})
        at, ch, ca = mcq("A value goes from 40 to 30. Which is correct?", ["25% decrease", "10% decrease", "33% decrease", "75% decrease"], "25% decrease")
        q.append({"question_text": "A value goes from 40 to 30. Which is correct?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.70, c=0.45, p=0.55, t=0.40, diag=0.65),
                  "hint_text": "Change is 10 out of original 40.",
                  "explanation_text": "10/40=25%.",
                  "likely_error_tags": ["percent_change_error"]})
        at, ch, ca = short_text("Explain what 'percent change' compares.", "Change relative to the original")
        q.append({"question_text": "Explain what 'percent change' compares.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.60, p=0.10, t=0.20, diag=0.50),
                  "hint_text": "Think: what is the base?",
                  "explanation_text": "Percent change compares the change to the original amount.",
                  "likely_error_tags": ["percent_change_concept_gap"]})
        return q

    if topic_id == "t_ratio_concepts":
        at, ch, ca = short_text("Write the ratio of 3 red to 5 blue as a fraction.", "3/5")
        q.append({"question_text": "Write the ratio of 3 red to 5 blue as a fraction.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.45, p=0.20, t=0.10, diag=0.55),
                  "hint_text": "Red:Blue = 3:5.",
                  "explanation_text": "3/5.",
                  "likely_error_tags": ["ratio_order_error"]})
        at, ch, ca = mcq("Which shows the same ratio as 2:3?", ["4:5", "4:6", "6:9", "3:6"], "4:6")
        q.append({"question_text": "Which shows the same ratio as 2:3?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.45, p=0.35, t=0.10, diag=0.60),
                  "hint_text": "Multiply both parts by the same number.",
                  "explanation_text": "2:3 ×2 = 4:6.",
                  "likely_error_tags": ["equivalence_error"]})
        at, ch, ca = short_text("In a class of 12 students, 7 are girls. What is the ratio of girls to total?", "7/12")
        q.append({"question_text": "In a class of 12 students, 7 are girls. What is the ratio of girls to total?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.50, p=0.25, t=0.30, diag=0.55),
                  "hint_text": "Girls:Total.",
                  "explanation_text": "7/12.",
                  "likely_error_tags": ["part_whole_confusion"]})
        at, ch, ca = mcq("Which is a part-to-part ratio?", ["3/10", "3 out of 10", "3:7", "30%"], "3:7")
        q.append({"question_text": "Which is a part-to-part ratio?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.55, p=0.10, t=0.10, diag=0.60),
                  "hint_text": "Part-to-part compares two parts, not part to whole.",
                  "explanation_text": "3:7 compares two parts.",
                  "likely_error_tags": ["ratio_type_confusion"]})
        return q

    if topic_id == "t_unit_rate":
        at, ch, ca = numeric("A car travels 150 km in 3 hours. What is the unit rate (km per hour)?", "50")
        q.append({"question_text": "A car travels 150 km in 3 hours. What is the unit rate (km per hour)?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.45, p=0.40, t=0.35, diag=0.60),
                  "hint_text": "Divide 150 by 3.",
                  "explanation_text": "50 km/h.",
                  "likely_error_tags": ["unit_rate_division_error"]})
        at, ch, ca = numeric("6 apples cost $3. What is the cost per apple?", "0.5")
        q.append({"question_text": "6 apples cost $3. What is the cost per apple?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.40, p=0.40, t=0.35, diag=0.55),
                  "hint_text": "Divide 3 by 6.",
                  "explanation_text": "$0.50 per apple.",
                  "likely_error_tags": ["divide_wrong_way"]})
        at, ch, ca = mcq("Which is a unit rate?", ["5 miles in 2 hours", "2:3", "$4 per 1 item", "25%"], "$4 per 1 item")
        q.append({"question_text": "Which is a unit rate?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.50, c=0.45, p=0.15, t=0.10, diag=0.55),
                  "hint_text": "Unit rate is per 1 unit.",
                  "explanation_text": "$4 per 1 item is per 1.",
                  "likely_error_tags": ["definition_error"]})
        at, ch, ca = short_text("A faucet fills 12 liters in 4 minutes. Unit rate?", "3 liters per minute")
        q.append({"question_text": "A faucet fills 12 liters in 4 minutes. Unit rate?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.45, p=0.35, t=0.35, diag=0.55),
                  "hint_text": "Divide 12 by 4.",
                  "explanation_text": "3 liters per minute.",
                  "likely_error_tags": ["unit_rate_division_error"]})
        return q

    if topic_id == "t_proportions":
        at, ch, ca = short_text("Solve: 2/3 = x/12", "8")
        q.append({"question_text": "Solve: 2/3 = x/12", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.70, c=0.50, p=0.60, t=0.15, diag=0.65),
                  "hint_text": "Cross-multiply: 2×12 = 3×x.",
                  "explanation_text": "24 = 3x so x=8.",
                  "likely_error_tags": ["cross_multiply_error"]})
        at, ch, ca = mcq("Which is proportional?", ["y=2x", "y=2x+1", "y=x^2", "y=3"], "y=2x")
        q.append({"question_text": "Which relationship is proportional?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.55, p=0.20, t=0.10, diag=0.60),
                  "hint_text": "Proportional means a constant ratio and passes through (0,0).",
                  "explanation_text": "y=2x is proportional.",
                  "likely_error_tags": ["proportional_definition_error"]})
        at, ch, ca = numeric("If 5 notebooks cost $15, how much do 8 notebooks cost (same price each)?", "24")
        q.append({"question_text": "If 5 notebooks cost $15, how much do 8 notebooks cost (same price each)?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.70, c=0.45, p=0.55, t=0.45, diag=0.65),
                  "hint_text": "Find unit rate: 15/5=3, then 3×8.",
                  "explanation_text": "24.",
                  "likely_error_tags": ["unit_rate_missing"]})
        at, ch, ca = short_text("Explain what it means for two ratios to be equivalent.", "They represent the same relationship")
        q.append({"question_text": "Explain what it means for two ratios to be equivalent.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.60, p=0.10, t=0.10, diag=0.45),
                  "hint_text": "Think: scaling both parts.",
                  "explanation_text": "Equivalent ratios can be made by multiplying/dividing both parts by the same number.",
                  "likely_error_tags": ["concept_gap"]})
        return q

    if topic_id == "t_scale_drawings":
        at, ch, ca = numeric("A map scale is 1 cm : 5 km. If two towns are 4 cm apart on the map, how far apart are they?", "20")
        q.append({"question_text": "A map scale is 1 cm : 5 km. If two towns are 4 cm apart on the map, how far apart are they?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.70, c=0.45, p=0.55, t=0.55, diag=0.65),
                  "hint_text": "Multiply 4 by 5.",
                  "explanation_text": "20 km.",
                  "likely_error_tags": ["scale_factor_error"]})
        at, ch, ca = mcq("A scale factor of 2 means the drawing is:", ["Half size", "Same size", "Double size", "Quarter size"], "Double size")
        q.append({"question_text": "A scale factor of 2 means the drawing is:", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.55, p=0.15, t=0.10, diag=0.55),
                  "hint_text": "Scale factor multiplies lengths.",
                  "explanation_text": "Lengths double.",
                  "likely_error_tags": ["scale_definition_error"]})
        at, ch, ca = numeric("A model is built at scale 1:10. A real length is 80 cm. Model length?", "8")
        q.append({"question_text": "A model is built at scale 1:10. A real length is 80 cm. Model length?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.45, t=0.40, diag=0.55),
                  "hint_text": "Divide by 10.",
                  "explanation_text": "8 cm.",
                  "likely_error_tags": ["invert_scale_error"]})
        at, ch, ca = short_text("Explain what a scale means in one sentence.", "It shows how drawing lengths compare to real lengths")
        q.append({"question_text": "Explain what a scale means in one sentence.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.60, p=0.10, t=0.10, diag=0.40),
                  "hint_text": "Think: drawing vs real.",
                  "explanation_text": "A scale tells how much real lengths are reduced or enlarged in a drawing.",
                  "likely_error_tags": ["definition_error"]})
        return q

    if topic_id == "t_simple_equations_1step":
        at, ch, ca = numeric("Solve: x + 7 = 19", "12")
        q.append({"question_text": "Solve: x + 7 = 19", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.40, c=0.40, p=0.30, t=0.10, diag=0.55),
                  "hint_text": "Subtract 7 from both sides.",
                  "explanation_text": "x=12.",
                  "likely_error_tags": ["inverse_operation_error"]})
        at, ch, ca = numeric("Solve: 5x = 35", "7")
        q.append({"question_text": "Solve: 5x = 35", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.35, p=0.35, t=0.10, diag=0.55),
                  "hint_text": "Divide by 5.",
                  "explanation_text": "x=7.",
                  "likely_error_tags": ["divide_wrong_side"]})
        at, ch, ca = numeric("Solve: x − 9 = 4", "13")
        q.append({"question_text": "Solve: x − 9 = 4", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.40, p=0.30, t=0.10, diag=0.60),
                  "hint_text": "Add 9 to both sides.",
                  "explanation_text": "x=13.",
                  "likely_error_tags": ["inverse_operation_error"]})
        at, ch, ca = numeric("A number minus 6 equals 15. What is the number?", "21")
        q.append({"question_text": "A number minus 6 equals 15. What is the number?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.45, p=0.30, t=0.35, diag=0.65),
                  "hint_text": "x−6=15.",
                  "explanation_text": "x=21.",
                  "likely_error_tags": ["word_to_equation_error"]})
        return q

    if topic_id == "t_simple_equations_2step":
        at, ch, ca = numeric("Solve: 3x + 5 = 20", "5")
        q.append({"question_text": "Solve: 3x + 5 = 20", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.55, t=0.15, diag=0.65),
                  "hint_text": "Subtract 5, then divide by 3.",
                  "explanation_text": "3x=15 so x=5.",
                  "likely_error_tags": ["order_of_inverse_ops_error"]})
        at, ch, ca = numeric("Solve: 4x − 8 = 12", "5")
        q.append({"question_text": "Solve: 4x − 8 = 12", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.70, c=0.45, p=0.60, t=0.15, diag=0.65),
                  "hint_text": "Add 8, then divide by 4.",
                  "explanation_text": "4x=20 so x=5.",
                  "likely_error_tags": ["inverse_operation_error"]})
        at, ch, ca = mcq("Which is the first step to solve 2x + 7 = 15?", ["Divide by 2", "Subtract 7", "Add 7", "Multiply by 2"], "Subtract 7")
        q.append({"question_text": "Which is the first step to solve 2x + 7 = 15?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.55, p=0.20, t=0.10, diag=0.60),
                  "hint_text": "Undo +7 first.",
                  "explanation_text": "Subtract 7 from both sides first.",
                  "likely_error_tags": ["procedure_confusion"]})
        at, ch, ca = short_text("Check the solution x=3 for 5x−1=14. Is it correct? (yes/no)", "yes")
        q.append({"question_text": "Check the solution x=3 for 5x−1=14. Is it correct? (yes/no)", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.40, t=0.15, diag=0.55),
                  "hint_text": "Substitute x=3.",
                  "explanation_text": "5(3)−1=15−1=14, so yes.",
                  "likely_error_tags": ["substitution_error"]})
        return q

    if topic_id == "t_expressions_distribute":
        at, ch, ca = short_text("Simplify: 3(2x + 4)", "6x+12")
        q.append({"question_text": "Simplify: 3(2x + 4)", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.45, p=0.55, t=0.10, diag=0.60),
                  "hint_text": "Multiply 3 by both terms.",
                  "explanation_text": "3×2x=6x and 3×4=12 → 6x+12.",
                  "likely_error_tags": ["distribution_error"]})
        at, ch, ca = short_text("Simplify: 5x + 2x − 3", "7x-3")
        q.append({"question_text": "Simplify: 5x + 2x − 3", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.35, p=0.55, t=0.10, diag=0.55),
                  "hint_text": "Combine like terms.",
                  "explanation_text": "5x+2x=7x, so 7x−3.",
                  "likely_error_tags": ["combine_like_terms_error"]})
        at, ch, ca = mcq("Which equals 2(x+3)?", ["2x+3", "2x+6", "x+6", "2x+9"], "2x+6")
        q.append({"question_text": "Which equals 2(x+3)?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.45, p=0.45, t=0.05, diag=0.60),
                  "hint_text": "Distribute 2.",
                  "explanation_text": "2x+6.",
                  "likely_error_tags": ["distribution_error"]})
        at, ch, ca = short_text("Simplify: −(x − 5)", "−x+5")
        q.append({"question_text": "Simplify: −(x − 5)", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.55, t=0.10, diag=0.65),
                  "hint_text": "Multiply everything inside by −1.",
                  "explanation_text": "−x + 5.",
                  "likely_error_tags": ["negative_distribution_error"]})
        return q

    if topic_id == "t_geometry_angle_basics":
        at, ch, ca = numeric("What is the measure of a straight angle?", "180")
        q.append({"question_text": "What is the measure of a straight angle?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.25, c=0.35, p=0.10, t=0.05, diag=0.35),
                  "hint_text": "A straight line is 180°.",
                  "explanation_text": "180.",
                  "likely_error_tags": ["angle_definition_error"]})
        at, ch, ca = numeric("Two angles are complementary. One is 35°. What is the other?", "55")
        q.append({"question_text": "Two angles are complementary. One is 35°. What is the other?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.45, p=0.30, t=0.10, diag=0.55),
                  "hint_text": "Complementary angles sum to 90°.",
                  "explanation_text": "90−35=55.",
                  "likely_error_tags": ["complementary_sum_error"]})
        at, ch, ca = numeric("Two angles are supplementary. One is 110°. What is the other?", "70")
        q.append({"question_text": "Two angles are supplementary. One is 110°. What is the other?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.45, p=0.30, t=0.10, diag=0.55),
                  "hint_text": "Supplementary angles sum to 180°.",
                  "explanation_text": "180−110=70.",
                  "likely_error_tags": ["supplementary_sum_error"]})
        at, ch, ca = mcq("An acute angle is:", ["less than 90°", "exactly 90°", "between 90° and 180°", "exactly 180°"], "less than 90°")
        q.append({"question_text": "An acute angle is:", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.30, c=0.40, p=0.10, t=0.05, diag=0.45),
                  "hint_text": "Acute means small.",
                  "explanation_text": "Acute angles are less than 90°.",
                  "likely_error_tags": ["angle_type_confusion"]})
        return q

    if topic_id == "t_area_perimeter":
        at, ch, ca = numeric("A rectangle is 8 cm by 3 cm. What is its perimeter?", "22")
        q.append({"question_text": "A rectangle is 8 cm by 3 cm. What is its perimeter?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.35, p=0.55, t=0.20, diag=0.55),
                  "hint_text": "Perimeter = 2(l+w).",
                  "explanation_text": "2(8+3)=22.",
                  "likely_error_tags": ["formula_confusion"]})
        at, ch, ca = numeric("A rectangle is 8 cm by 3 cm. What is its area?", "24")
        q.append({"question_text": "A rectangle is 8 cm by 3 cm. What is its area?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.35, p=0.55, t=0.20, diag=0.55),
                  "hint_text": "Area = l×w.",
                  "explanation_text": "8×3=24.",
                  "likely_error_tags": ["area_perimeter_confusion"]})
        at, ch, ca = numeric("A triangle has base 10 cm and height 6 cm. What is its area?", "30")
        q.append({"question_text": "A triangle has base 10 cm and height 6 cm. What is its area?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.60, c=0.40, p=0.60, t=0.20, diag=0.60),
                  "hint_text": "Area = 1/2 × base × height.",
                  "explanation_text": "1/2×10×6=30.",
                  "likely_error_tags": ["missing_half_factor"]})
        at, ch, ca = short_text("Explain the difference between area and perimeter.", "Area is inside; perimeter is boundary")
        q.append({"question_text": "Explain the difference between area and perimeter.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.60, p=0.10, t=0.15, diag=0.45),
                  "hint_text": "Think inside vs around.",
                  "explanation_text": "Area measures the inside space; perimeter measures the distance around.",
                  "likely_error_tags": ["concept_gap"]})
        return q

    if topic_id == "t_circle_basics":
        at, ch, ca = numeric("A circle has radius 5 cm. What is its diameter?", "10")
        q.append({"question_text": "A circle has radius 5 cm. What is its diameter?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.40, p=0.40, t=0.10, diag=0.50),
                  "hint_text": "Diameter = 2×radius.",
                  "explanation_text": "10 cm.",
                  "likely_error_tags": ["radius_diameter_confusion"]})
        at, ch, ca = short_text("Name the line segment from the center to the circle.", "radius")
        q.append({"question_text": "Name the line segment from the center to the circle.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.35, c=0.45, p=0.05, t=0.05, diag=0.40),
                  "hint_text": "It starts at the center.",
                  "explanation_text": "Radius.",
                  "likely_error_tags": ["vocabulary_error"]})
        at, ch, ca = numeric("Use π≈3.14. A circle has diameter 10 cm. Estimate its circumference.", "31.4")
        q.append({"question_text": "Use π≈3.14. A circle has diameter 10 cm. Estimate its circumference.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.55, t=0.20, diag=0.55),
                  "hint_text": "Circumference ≈ π×d.",
                  "explanation_text": "3.14×10=31.4.",
                  "likely_error_tags": ["formula_error"]})
        at, ch, ca = mcq("If the radius doubles, the circumference:", ["stays same", "doubles", "triples", "halves"], "doubles")
        q.append({"question_text": "If the radius doubles, the circumference:", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.70, c=0.55, p=0.25, t=0.25, diag=0.60),
                  "hint_text": "C = 2πr.",
                  "explanation_text": "If r doubles, C doubles.",
                  "likely_error_tags": ["proportional_reasoning_error"]})
        return q

    if topic_id == "t_volume_rect_prism":
        at, ch, ca = numeric("Find the volume of a box 4 cm × 3 cm × 5 cm.", "60")
        q.append({"question_text": "Find the volume of a box 4 cm × 3 cm × 5 cm.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.40, p=0.60, t=0.20, diag=0.55),
                  "hint_text": "Volume = l×w×h.",
                  "explanation_text": "4×3×5=60 cubic cm.",
                  "likely_error_tags": ["multiply_error"]})
        at, ch, ca = numeric("A rectangular prism has base 6 cm by 2 cm and height 5 cm. Volume?", "60")
        q.append({"question_text": "A rectangular prism has base 6 cm by 2 cm and height 5 cm. Volume?", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.65, c=0.45, p=0.60, t=0.20, diag=0.55),
                  "hint_text": "Base area × height.",
                  "explanation_text": "(6×2)×5=60.",
                  "likely_error_tags": ["formula_confusion"]})
        at, ch, ca = mcq("Volume is measured in:", ["cm", "cm^2", "cm^3", "degrees"], "cm^3")
        q.append({"question_text": "Volume is measured in:", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.45, c=0.45, p=0.10, t=0.05, diag=0.45),
                  "hint_text": "Think cubes.",
                  "explanation_text": "Cubic units (cm^3).",
                  "likely_error_tags": ["units_error"]})
        at, ch, ca = short_text("Explain in one sentence what volume means.", "How much space an object takes up")
        q.append({"question_text": "Explain in one sentence what volume means.", "answer_type": at, "choices": ch, "correct_answer": ca,
                  **base_meta(difficulty=0.55, c=0.60, p=0.10, t=0.10, diag=0.40),
                  "hint_text": "Space inside.",
                  "explanation_text": "Volume is the amount of space inside or taken up by a 3D object.",
                  "likely_error_tags": ["concept_gap"]})
        return q

    # Default fallback: create generic questions so every topic has coverage
    # (This keeps the demo within locked scope even for sparsely connected topics.)
    at, ch, ca = mcq(f"In topic {topic_id}, which statement best matches 'easy practice'?", ["A", "B", "C", "D"], "A")
    q.append({"question_text": f"In topic {topic_id}, choose the easiest option (demo placeholder).", "answer_type": at, "choices": ch, "correct_answer": ca,
              **base_meta(difficulty=0.40, c=0.30, p=0.20, t=0.05, diag=0.30),
              "hint_text": "Pick A.",
              "explanation_text": "This is a placeholder question used only to keep the demo complete.",
              "likely_error_tags": ["placeholder"]})
    at, ch, ca = numeric(f"Demo numeric question for {topic_id}: What is 7+5?", "12")
    q.append({"question_text": f"Demo numeric question for {topic_id}: What is 7+5?", "answer_type": at, "choices": ch, "correct_answer": ca,
              **base_meta(difficulty=0.45, c=0.20, p=0.30, t=0.05, diag=0.25),
              "hint_text": "Add.",
              "explanation_text": "12.",
              "likely_error_tags": ["placeholder"]})
    at, ch, ca = short_text(f"Demo short question for {topic_id}: write 'ok'", "ok")
    q.append({"question_text": f"Demo short question for {topic_id}: write 'ok'", "answer_type": at, "choices": ch, "correct_answer": ca,
              **base_meta(difficulty=0.50, c=0.20, p=0.20, t=0.05, diag=0.20),
              "hint_text": "Type ok.",
              "explanation_text": "ok",
              "likely_error_tags": ["placeholder"]})
    at, ch, ca = short_text(f"Demo transfer question for {topic_id}: explain why practice matters.", "To learn")
    q.append({"question_text": f"Demo transfer question for {topic_id}: explain why practice matters.", "answer_type": at, "choices": ch, "correct_answer": ca,
              **base_meta(difficulty=0.60, c=0.50, p=0.10, t=0.35, diag=0.25),
              "hint_text": "Think learning.",
              "explanation_text": "Practice builds understanding and speed.",
              "likely_error_tags": ["placeholder"]})
    return q


EXTRA_TOPICS = {
    # Add a 5th question to hit ~150 total and strengthen key demo topics.
    "t_percent_of_quantity",
    "t_fraction_add_sub_unlike",
    "t_decimal_div",
    "t_proportions",
    "t_simple_equations_2step",
    "t_integer_expressions",
    "t_area_perimeter",
    "t_fraction_div",
    "t_percent_change",
    "t_unit_rate",
    "t_scale_drawings",
    "t_decimal_mult",
    "t_compare_fractions",
    "t_fraction_mult",
}


def add_fifth_question(topic_id: str) -> Dict:
    # Simple extra diagnostic/transfer item, deterministic per topic.
    at, ch, ca = mcq("Which choice is most reasonable?", ["A", "B", "C", "D"], "B")
    return {
        "question_text": f"Extra diagnostic (demo) for {topic_id}: Which choice is most reasonable?",
        "answer_type": at,
        "choices": ch,
        "correct_answer": ca,
        **base_meta(difficulty=0.65, c=0.45, p=0.20, t=0.25, diag=0.55),
        "hint_text": "Pick B for this demo diagnostic.",
        "explanation_text": "This is an extra diagnostic item to vary difficulty and triggers in the demo.",
        "likely_error_tags": ["diagnostic_placeholder"],
    }


def main() -> None:
    payload = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    topics = payload.get("topics", [])

    all_questions: List[Dict] = []
    for t in topics:
        tid = t["id"]
        qs = topic_questions(tid)
        # Attach required fields and ids
        out_qs = []
        for i, item in enumerate(qs, start=1):
            out_qs.append(
                {
                    "id": qid(tid, i),
                    "topic_id": tid,
                    "secondary_topic_ids": item.get("secondary_topic_ids", []),
                    "question_text": item["question_text"],
                    "answer_type": item["answer_type"],
                    "choices": item.get("choices", []),
                    "correct_answer": str(item["correct_answer"]),
                    "difficulty_prior": float(item["difficulty_prior"]),
                    "conceptual_load": float(item["conceptual_load"]),
                    "procedural_load": float(item["procedural_load"]),
                    "transfer_load": float(item["transfer_load"]),
                    "diagnostic_value": float(item["diagnostic_value"]),
                    "hint_text": item.get("hint_text", ""),
                    "explanation_text": item.get("explanation_text", ""),
                    "likely_error_tags": item.get("likely_error_tags", []),
                }
            )
        if tid in EXTRA_TOPICS:
            extra = add_fifth_question(tid)
            out_qs.append(
                {
                    "id": qid(tid, len(out_qs) + 1),
                    "topic_id": tid,
                    "secondary_topic_ids": [],
                    "question_text": extra["question_text"],
                    "answer_type": extra["answer_type"],
                    "choices": extra.get("choices", []),
                    "correct_answer": str(extra["correct_answer"]),
                    "difficulty_prior": float(extra["difficulty_prior"]),
                    "conceptual_load": float(extra["conceptual_load"]),
                    "procedural_load": float(extra["procedural_load"]),
                    "transfer_load": float(extra["transfer_load"]),
                    "diagnostic_value": float(extra["diagnostic_value"]),
                    "hint_text": extra.get("hint_text", ""),
                    "explanation_text": extra.get("explanation_text", ""),
                    "likely_error_tags": extra.get("likely_error_tags", []),
                }
            )

        all_questions.extend(out_qs)

    out = {
        "question_format_version": "v1",
        "generated_from": str(GRAPH_PATH),
        "question_count": len(all_questions),
        "questions": all_questions,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"OK: wrote {len(all_questions)} questions to {OUT_PATH}")


if __name__ == "__main__":
    main()

