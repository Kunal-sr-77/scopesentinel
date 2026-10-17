from __future__ import annotations

import unittest

from scopesentinel.agreement import parse_agreement, parse_clause
from scopesentinel.domain import ClauseType


class AgreementParsingTests(unittest.TestCase):
    def test_parse_clause_does_not_rewrite_the_source_text(self) -> None:
        source = "  Logo design is excluded.  "

        clause = parse_clause(source, clause_id="x-logo")

        self.assertEqual(clause.source_text, source)
        self.assertEqual(clause.id, "x-logo")

    def test_parse_clause_preserves_source_text_and_assigns_a_typed_id(self) -> None:
        source = "Up to 5 responsive marketing pages, including landing pages."

        clause = parse_clause(source, clause_id="d-pages")

        self.assertEqual(clause.id, "d-pages")
        self.assertEqual(clause.type, ClauseType.DELIVERABLE)
        self.assertEqual(clause.source_text, source)
        self.assertEqual(clause.quantity, 5)
        self.assertEqual(clause.unit, "page")
        self.assertIn("marketing page", clause.concepts)
        self.assertIn("landing page", clause.concepts)

    def test_parse_agreement_keeps_each_source_clause_and_typed_categories(self) -> None:
        agreement = parse_agreement(
            "\n".join(
                (
                    "Up to 3 responsive marketing pages are included.",
                    "Logo design is excluded.",
                    "Two revision rounds per page are included.",
                    "Approved additional work is billed at $125 per hour.",
                    "The agreed launch deadline is 30 November 2026.",
                )
            )
        )

        self.assertEqual(
            [clause.type for clause in agreement.clauses],
            [
                ClauseType.DELIVERABLE,
                ClauseType.EXCLUSION,
                ClauseType.LIMIT,
                ClauseType.RATE,
                ClauseType.DEADLINE,
            ],
        )
        self.assertEqual(
            [clause.source_text for clause in agreement.clauses],
            [
                "Up to 3 responsive marketing pages are included.",
                "Logo design is excluded.",
                "Two revision rounds per page are included.",
                "Approved additional work is billed at $125 per hour.",
                "The agreed launch deadline is 30 November 2026.",
            ],
        )
