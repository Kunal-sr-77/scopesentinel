from __future__ import annotations

import unittest

from scopesentinel.evaluation import EVALUATION_CASES, evaluation_agreement


class EvaluationSetTests(unittest.TestCase):
    def test_fixed_set_has_at_least_fifteen_unique_labels(self) -> None:
        self.assertGreaterEqual(len(EVALUATION_CASES), 15)
        self.assertEqual(len({case.id for case in EVALUATION_CASES}), len(EVALUATION_CASES))

    def test_worked_examples_a_to_e_are_present(self) -> None:
        self.assertEqual({case.id for case in EVALUATION_CASES[:5]}, {"A", "B", "C", "D", "E"})

    def test_deadline_cases_freeze_clarification_precedence(self) -> None:
        conflict = next(case for case in EVALUATION_CASES if case.id == "L")
        combined = next(case for case in EVALUATION_CASES if case.id == "P")
        self.assertEqual(conflict.expected_classification, "NEEDS_CLARIFICATION")
        self.assertEqual(combined.expected_classification, "NEEDS_CLARIFICATION")
        self.assertEqual(conflict.expected_scheduling_flag, "deadline_conflict")

    def test_case_variants_preserve_their_expected_inputs(self) -> None:
        self.assertNotIn(
            "r-page-effort",
            {clause.id for clause in evaluation_agreement("no_effort_assumption").clauses},
        )
        self.assertEqual(evaluation_agreement("four_pages_used").current_usage["marketing_page"], 4)
        self.assertNotIn("marketing_page", evaluation_agreement("unknown_page_usage").current_usage)
