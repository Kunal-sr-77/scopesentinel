from __future__ import annotations

import unittest

from scopesentinel.analysis import analyze_request, parse_request, retrieve_evidence
from scopesentinel.domain import (
    Agreement,
    Classification,
    Clause,
    ClauseType,
    EvidenceHit,
    ParseOutput,
    Request,
    RetrieveOutput,
)
from scopesentinel.evaluation import EVALUATION_CASES, evaluation_agreement


def _case(case_id: str):
    return next(case for case in EVALUATION_CASES if case.id == case_id)


def _request(case_id: str) -> Request:
    case = _case(case_id)
    return Request(
        id=f"request-{case_id.lower()}",
        project_id="project-1",
        text=case.request_text,
    )


class FixedWorkedExampleTests(unittest.TestCase):
    def test_cases_a_to_e_have_the_frozen_classification_evidence_and_tags(self) -> None:
        for case_id in ("A", "B", "C", "D", "E"):
            with self.subTest(case=case_id):
                case = _case(case_id)
                result = analyze_request(
                    _request(case_id), evaluation_agreement(case.agreement_variant)
                )

                self.assertEqual(result.classification.value, case.expected_classification)
                self.assertEqual(
                    result.evidence_clause_ids, list(case.expected_evidence_clause_ids)
                )
                self.assertEqual(
                    result.trace.classify.uncertainty_tags,
                    list(case.expected_uncertainty_tags),
                )

    def test_case_a_preserves_typed_source_evidence_and_populates_every_stage(self) -> None:
        result = analyze_request(_request("A"), evaluation_agreement())

        self.assertIsInstance(result.trace.parse, ParseOutput)
        self.assertIsInstance(result.trace.retrieve, RetrieveOutput)
        self.assertIsInstance(result.trace.retrieve.hits[0], EvidenceHit)
        self.assertEqual(result.trace.retrieve.hits[0].clause_id, "d-marketing-pages")
        self.assertEqual(result.trace.retrieve.hits[0].clause_type.value, "deliverable")
        self.assertEqual(
            result.trace.retrieve.hits[0].source_text,
            "Up to 5 responsive marketing pages, including landing and case-study pages.",
        )
        self.assertIsNotNone(result.trace.draft)
        self.assertIs(result.draft, result.trace.draft)

    def test_remaining_fixed_cases_match_their_frozen_contract(self) -> None:
        for case in EVALUATION_CASES[5:]:
            with self.subTest(case=case.id):
                result = analyze_request(
                    _request(case.id), evaluation_agreement(case.agreement_variant)
                )

                self.assertEqual(result.classification.value, case.expected_classification)
                self.assertEqual(result.evidence_clause_ids, list(case.expected_evidence_clause_ids))
                self.assertEqual(result.trace.classify.uncertainty_tags, list(case.expected_uncertainty_tags))
                self.assertEqual(result.scheduling_flag, case.expected_scheduling_flag)

    def test_deadline_conflict_wins_over_scope_and_is_never_out_of_scope(self) -> None:
        result = analyze_request(_request("P"), evaluation_agreement())

        self.assertEqual(result.classification, Classification.NEEDS_CLARIFICATION)
        self.assertEqual(result.scheduling_flag, "deadline_conflict")
        self.assertNotEqual(result.classification, Classification.POTENTIALLY_OUT_OF_SCOPE)


class EvidenceAndEstimateTests(unittest.TestCase):
    def test_retrieval_returns_typed_evidence_before_classification(self) -> None:
        parsed = parse_request("Please write the homepage copy for us.")
        retrieved = retrieve_evidence(parsed, evaluation_agreement())

        self.assertEqual([hit.clause_id for hit in retrieved.hits], ["x-copywriting"])
        self.assertEqual(retrieved.hits[0].clause_type, ClauseType.EXCLUSION)
        self.assertEqual(retrieved.hits[0].source_text, "Copywriting and creation of new marketing copy are excluded.")

    def test_estimate_requires_both_an_effort_assumption_and_hourly_rate(self) -> None:
        complete = analyze_request("Please add one additional marketing page.", evaluation_agreement())
        incomplete = analyze_request(
            "Please add one additional marketing page.",
            evaluation_agreement("no_effort_assumption"),
        )

        self.assertEqual(complete.draft.estimated_hours, 4)
        self.assertEqual(complete.draft.estimated_cost, 500)
        self.assertIsNone(incomplete.draft.estimated_hours)
        self.assertIsNone(incomplete.draft.estimated_cost)

    def test_contradictory_typed_clauses_require_clarification(self) -> None:
        agreement = Agreement(
            clauses=[
                Clause(
                    id="d-analytics",
                    type=ClauseType.DELIVERABLE,
                    source_text="Analytics reporting is included.",
                    subtype="analytics",
                    concepts=("analytics",),
                ),
                Clause(
                    id="x-analytics",
                    type=ClauseType.EXCLUSION,
                    source_text="Analytics reporting is excluded.",
                    subtype="analytics",
                    concepts=("analytics",),
                ),
            ]
        )

        result = analyze_request("Please provide analytics reporting.", agreement)

        self.assertEqual(result.classification, Classification.NEEDS_CLARIFICATION)
        self.assertEqual(result.conflicting_clause_ids, ["d-analytics", "x-analytics"])
        self.assertEqual(result.trace.retrieve.conflict_clause_ids, ["d-analytics", "x-analytics"])

    def test_no_evidence_is_clarification_and_not_an_exclusion(self) -> None:
        result = analyze_request(_request("K"), evaluation_agreement())

        self.assertEqual(result.classification, Classification.NEEDS_CLARIFICATION)
        self.assertEqual(result.evidence_clause_ids, [])
        self.assertIn("no_matching_clause", result.trace.classify.uncertainty_tags)
        self.assertNotIn("excluded_work", result.trace.classify.uncertainty_tags)

    def test_empty_request_is_clarification(self) -> None:
        result = analyze_request("", evaluation_agreement())

        self.assertEqual(result.classification, Classification.NEEDS_CLARIFICATION)
        self.assertEqual(result.trace.classify.uncertainty_tags, ["no_matching_clause"])


class RequestParsingTests(unittest.TestCase):
    def test_parser_extracts_action_quantity_unit_synonyms_qualifiers_and_ambiguity(self) -> None:
        parsed = parse_request(
            "Please add two landing pages for mobile, and improve SEO without changing copy."
        )

        self.assertEqual(parsed.normalized_text, parsed.normalized_text.lower())
        self.assertEqual(len(parsed.items), 2)
        page_item, seo_item = parsed.items
        self.assertEqual(page_item.intent, "add")
        self.assertEqual(page_item.quantity, 2)
        self.assertEqual(page_item.unit, "page")
        self.assertIn("marketing page", page_item.concepts)
        self.assertIn("mobile", page_item.qualifiers)
        self.assertEqual(seo_item.intent, "improve")
        self.assertIn("seo", seo_item.concepts)
        self.assertIn("seo_meaning_ambiguous", seo_item.ambiguity_tags)
