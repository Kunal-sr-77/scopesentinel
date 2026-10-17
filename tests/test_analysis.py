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
    def test_every_evaluation_result_has_rationale_and_decision_rules(self) -> None:
        for case in EVALUATION_CASES:
            with self.subTest(case=case.id):
                result = analyze_request(
                    _request(case.id), evaluation_agreement(case.agreement_variant)
                )
                self.assertTrue(result.trace.classify.rationale)
                self.assertTrue(all(sentence.strip() for sentence in result.trace.classify.rationale))
                self.assertTrue(result.trace.classify.decision_rules)

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

    def test_mixed_request_keeps_supported_page_estimate_when_logo_effort_is_missing(self) -> None:
        result = analyze_request(
            "Please add two case-study pages and design a new logo.",
            evaluation_agreement(),
        )

        self.assertEqual(result.draft.estimated_hours, 8)
        self.assertEqual(result.draft.estimated_cost, 1000)
        self.assertIn("2 pages", result.draft.estimate_label)
        self.assertIn("4 hours", result.draft.estimate_label)
        self.assertIn("8 estimated hours", result.draft.estimate_label)
        self.assertIn("$1,000", result.draft.estimate_label)
        self.assertIn("logo", result.draft.estimate_label.lower())
        self.assertIn("not included", result.draft.estimate_label.lower())

        rationale = " ".join(result.trace.classify.rationale).lower()
        self.assertIn("d-marketing-pages", rationale)
        self.assertIn("x-logo-design", rationale)
        self.assertIn("5 of 5", rationale)
        self.assertIn("2 more", rationale)
        self.assertIn("r-page-effort", rationale)
        self.assertIn("r-hourly-rate", rationale)
        self.assertNotIn("case-study pages are excluded", rationale)

    def test_seo_clarification_draft_asks_about_included_metadata_or_excluded_strategy(self) -> None:
        result = analyze_request("Please improve SEO.", evaluation_agreement())

        questions = " ".join(result.draft.clarification_questions).lower()
        self.assertEqual(result.classification, Classification.NEEDS_CLARIFICATION)
        self.assertIn("metadata", questions)
        self.assertIn("included", questions)
        self.assertIn("up to 5 pages", questions)
        self.assertIn("strategy", questions)
        self.assertIn("keyword research", questions)
        self.assertIn("excluded", questions)
        self.assertIn("?", result.draft.body)

    def test_vague_design_clarification_draft_asks_for_pages_and_specific_changes(self) -> None:
        result = analyze_request("Please make the site feel more premium.", evaluation_agreement())

        questions = " ".join(result.draft.clarification_questions).lower()
        self.assertIn("which pages", questions)
        self.assertIn("specific changes", questions)

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

    def test_no_evidence_draft_uses_plain_new_work_question(self) -> None:
        result = analyze_request(_request("K"), evaluation_agreement())

        questions = " ".join(result.draft.clarification_questions).lower()
        self.assertIn("does not match any listed deliverable or exclusion", questions)
        self.assertIn("confirm whether it is new work", questions)
        self.assertNotIn("which agreed deliverable or contract clause", questions)

    def test_preserved_logo_is_context_evidence_not_an_exclusion(self) -> None:
        parsed = parse_request("Please keep the logo as is and update the footer.")
        retrieved = retrieve_evidence(parsed, evaluation_agreement())
        result = analyze_request("Please keep the logo as is and update the footer.", evaluation_agreement())

        logo_hit = next(hit for hit in retrieved.hits if hit.clause_id == "x-logo-design")
        self.assertEqual(logo_hit.relation, "context")
        self.assertIn("preservation", logo_hit.matched_constraints)
        self.assertNotEqual(result.classification, Classification.POTENTIALLY_OUT_OF_SCOPE)
        self.assertIn("does not trigger the exclusion", " ".join(result.trace.classify.rationale).lower())

    def test_empty_request_is_clarification(self) -> None:
        result = analyze_request("", evaluation_agreement())

        self.assertEqual(result.classification, Classification.NEEDS_CLARIFICATION)
        self.assertEqual(result.trace.classify.uncertainty_tags, ["no_matching_clause"])


class RequestParsingTests(unittest.TestCase):
    def test_digit_ordinals_one_through_five_drive_revision_scope(self) -> None:
        expected = {
            "1st": Classification.IN_SCOPE,
            "2nd": Classification.IN_SCOPE,
            "3rd": Classification.POTENTIALLY_OUT_OF_SCOPE,
            "4th": Classification.POTENTIALLY_OUT_OF_SCOPE,
            "5th": Classification.POTENTIALLY_OUT_OF_SCOPE,
        }
        for ordinal, classification in expected.items():
            with self.subTest(ordinal=ordinal):
                text = f"Can you do a {ordinal} round of changes on the pricing page?"
                parsed = parse_request(text)
                result = analyze_request(text, evaluation_agreement())
                self.assertEqual(parsed.items[0].intent, "revise")
                self.assertEqual(result.classification, classification)
                self.assertIn("l-revision-rounds", result.evidence_clause_ids)

    def test_concept_chips_drop_phrase_fragments_and_repeated_noise(self) -> None:
        parsed = parse_request("Please improve SEO and add two case-study pages; improve the layout.")
        concepts = [concept for item in parsed.items for concept in item.concepts]

        self.assertIn("case-study page", concepts)
        self.assertNotIn("case", concepts)
        self.assertNotIn("study", concepts)
        self.assertNotIn("pages", concepts)
        self.assertNotIn("improve", concepts)
        self.assertEqual(concepts.count("case-study page"), 1)

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
