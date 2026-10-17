from __future__ import annotations

import json
import unittest
from typing import Any

from scopesentinel.analysis import analyze_request
from scopesentinel.domain import Request
from scopesentinel.evaluation import EVALUATION_CASES

try:
    from .holdout_cases import HOLDOUT_CASES, HoldoutCase, agreement_for
except ImportError:  # unittest discover -s tests loads test modules top-level.
    from holdout_cases import HOLDOUT_CASES, HoldoutCase, agreement_for


def _request(case: HoldoutCase) -> Request:
    return Request(id=f"holdout-{case.id.lower()}", project_id="project-1", text=case.request_text)


def _actual(case: HoldoutCase) -> dict[str, Any]:
    result = analyze_request(_request(case), agreement_for(case))
    actual: dict[str, Any] = {
        "classification": result.classification.value,
        "evidence_clause_ids": result.evidence_clause_ids,
        "uncertainty_tags": result.trace.classify.uncertainty_tags,
        "scheduling_flag": result.scheduling_flag,
    }
    if case.check_estimate:
        actual["estimated_hours"] = result.draft.estimated_hours if result.draft else None
        actual["estimated_cost"] = result.draft.estimated_cost if result.draft else None
    return actual


def _expected(case: HoldoutCase) -> dict[str, Any]:
    expected: dict[str, Any] = {
        "classification": case.expected_classification,
        "evidence_clause_ids": list(case.expected_evidence_clause_ids),
        "uncertainty_tags": list(case.expected_uncertainty_tags),
        "scheduling_flag": case.expected_scheduling_flag,
    }
    if case.check_estimate:
        expected["estimated_hours"] = case.expected_estimated_hours
        expected["estimated_cost"] = case.expected_estimated_cost
    return expected


def evaluate_holdout() -> dict[str, Any]:
    """Return a JSON-serializable strict holdout report."""

    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for case in HOLDOUT_CASES:
        expected = _expected(case)
        actual = _actual(case)
        mismatches = {
            field: {"expected": expected[field], "actual": actual[field]}
            for field in expected
            if expected[field] != actual[field]
        }
        record = {
            "id": case.id,
            "label": case.label,
            "request_text": case.request_text,
            "expected": expected,
            "actual": actual,
            "passed": not mismatches,
            "mismatches": mismatches,
        }
        records.append(record)
        if mismatches:
            failures.append(record)
    total = len(records)
    return {
        "total": total,
        "strict_correct": total - len(failures),
        "strict_accuracy": (total - len(failures)) / total if total else 0.0,
        "failures": failures,
        "cases": records,
    }


class HoldoutFixtureTests(unittest.TestCase):
    def test_holdout_is_new_and_covers_the_required_traps(self) -> None:
        original_ids = {case.id for case in EVALUATION_CASES}
        original_requests = {case.request_text for case in EVALUATION_CASES}
        self.assertGreaterEqual(len(HOLDOUT_CASES), 12)
        self.assertTrue({case.id for case in HOLDOUT_CASES}.isdisjoint(original_ids))
        self.assertTrue(
            {case.request_text for case in HOLDOUT_CASES}.isdisjoint(original_requests)
        )
        self.assertGreaterEqual(
            sum(case.false_positive_trap for case in HOLDOUT_CASES),
            4,
        )

    def test_fixed_holdout_report_is_strict_and_machine_readable(self) -> None:
        report = evaluate_holdout()
        print(json.dumps(report, sort_keys=True))
        self.assertEqual(
            report["failures"],
            [],
            msg=json.dumps(report, indent=2, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
