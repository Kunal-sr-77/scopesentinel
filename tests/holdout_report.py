"""Non-failing command-line report for the independent holdout evaluation."""

from __future__ import annotations

import json

from .test_holdout import evaluate_holdout


def main() -> None:
    report = evaluate_holdout()
    print(
        f"Holdout accuracy: {report['strict_correct']}/{report['total']} "
        f"({report['strict_accuracy']:.2%})"
    )
    if not report["failures"]:
        print("Failures: none")
        return
    print("Failures:")
    for failure in report["failures"]:
        print(f"- {failure['id']}: {failure['label']}")
        print(json.dumps(failure["mismatches"], sort_keys=True))


if __name__ == "__main__":
    main()
