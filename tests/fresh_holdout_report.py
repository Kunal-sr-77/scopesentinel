"""Non-failing machine-readable report for the fresh independent holdout."""

from __future__ import annotations

import json
from typing import Any

from scopesentinel.analysis import analyze_request
from scopesentinel.domain import Request

from .fresh_holdout_cases import FRESH_HOLDOUT_CASES, FreshHoldoutCase, agreement_for


def _actual(case: FreshHoldoutCase) -> dict[str, Any]:
    result = analyze_request(
        Request(
            id=f"fresh-holdout-{case.id.lower()}",
            project_id="project-1",
            text=case.request_text,
        ),
        agreement_for(case),
    )
    actual: dict[str, Any] = {
        "classification": result.classification.value,
        "evidence_clause_ids": result.evidence_clause_ids,
        "uncertainty_tags": result.trace.classify.uncertainty_tags,
        "scheduling_flag": result.scheduling_flag,
    }
    if case.check_estimate:
        actual["estimated_hours"] = result.draft.estimated_hours if result.draft else None
        actual["estimated_cost"] = result.draft.estimated_cost if result.draft else None
        actual["estimate_label"] = result.draft.estimate_label if result.draft else None
    return actual


def _expected(case: FreshHoldoutCase) -> dict[str, Any]:
    expected: dict[str, Any] = {
        "classification": case.expected_classification,
        "evidence_clause_ids": list(case.expected_evidence_clause_ids),
        "uncertainty_tags": list(case.expected_uncertainty_tags),
        "scheduling_flag": case.expected_scheduling_flag,
    }
    if case.check_estimate:
        expected["estimated_hours"] = case.expected_estimated_hours
        expected["estimated_cost"] = case.expected_estimated_cost
        expected["estimate_label"] = case.expected_estimate_label
    return expected


def evaluate_fresh_holdout() -> dict[str, Any]:
    """Return a JSON-serializable strict report without raising on failures."""

    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for case in FRESH_HOLDOUT_CASES:
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
    strict_correct = total - len(failures)
    return {
        "total": total,
        "strict_correct": strict_correct,
        "strict_accuracy": strict_correct / total if total else 0.0,
        "false_positive_traps": sum(case.false_positive_trap for case in FRESH_HOLDOUT_CASES),
        "failures": failures,
        "cases": records,
    }


def main() -> None:
    report = evaluate_fresh_holdout()
    summary = {
        "suite": "fresh_holdout",
        "total": report["total"],
        "strict_correct": report["strict_correct"],
        "strict_accuracy": report["strict_accuracy"],
        "false_positive_traps": report["false_positive_traps"],
        "failure_count": len(report["failures"]),
    }
    print(f"FRESH_HOLDOUT_SUMMARY {json.dumps(summary, sort_keys=True)}")
    if not report["failures"]:
        print("FRESH_HOLDOUT_FAILURES none")
        return
    for failure in report["failures"]:
        print(
            f"FRESH_HOLDOUT_FAILURE {failure['id']}: {failure['label']}"
        )
        print(json.dumps(failure["mismatches"], sort_keys=True))


if __name__ == "__main__":
    main()
