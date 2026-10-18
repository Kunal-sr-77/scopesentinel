from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scopesentinel.analysis import analyze_request
from scopesentinel.domain import ClauseType, Request
from scopesentinel.evaluation import EVALUATION_CASES, evaluation_agreement
from scopesentinel.store import JsonHistoryStore
from scopesentinel.web import create_app
from tests.fresh_holdout_cases import FRESH_HOLDOUT_CASES
from tests.holdout_cases import HOLDOUT_CASES


class WebWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = JsonHistoryStore(Path(self.temp_dir.name) / "history.json")
        self.app = create_app(store=self.store)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _setup_form_project(self, variant: str = "standard"):
        agreement = evaluation_agreement(variant)
        values = {
            "project_name": "Northstar Marketing Site",
            "client_name": "Northstar Studio",
            "deliverables": "\n".join(
                clause.source_text
                for clause in agreement.clauses
                if clause.type is ClauseType.DELIVERABLE
            ),
            "exclusions": "\n".join(
                clause.source_text
                for clause in agreement.clauses
                if clause.type is ClauseType.EXCLUSION
            ),
            "limits": "\n".join(
                clause.source_text
                for clause in agreement.clauses
                if clause.type is ClauseType.LIMIT
            ),
            "deadlines": "\n".join(
                clause.source_text
                for clause in agreement.clauses
                if clause.type is ClauseType.DEADLINE
            ),
            "pricing": "\n".join(
                clause.source_text
                for clause in agreement.clauses
                if clause.type is ClauseType.RATE
            ),
            "pages_delivered": str(agreement.current_usage.get("marketing_page", "")),
            "hourly_rate": str(agreement.pricing_rules.get("hourly_rate", "")),
            "page_effort": str(
                agreement.pricing_rules.get("effort_hours", {}).get(
                    "additional_marketing_page", ""
                )
            ),
        }
        response = self.client.post("/setup", data=values)
        self.assertEqual(response.status_code, 302)
        return agreement, self.app.config["PROJECT"].agreement

    def test_setup_request_analysis_evidence_trace_and_approval_flow(self) -> None:
        setup = self.client.get("/setup")
        self.assertEqual(setup.status_code, 200)
        self.assertIn(b"Current usage and estimates", setup.data)

        saved = self.client.post(
            "/setup",
            data={
                "project_name": "Demo Site",
                "client_name": "Demo Client",
                "deliverables": "Up to 5 responsive marketing pages.",
                "exclusions": "Logo design is excluded.",
                "limits": "Two revision rounds per page are included.",
                "deadlines": "The agreed launch deadline is 30 November 2026.",
                "pricing": "Approved additional work is billed at $125 per hour.",
                "pages_delivered": "0",
                "hourly_rate": "125",
                "page_effort": "4",
            },
        )
        self.assertEqual(saved.status_code, 302)

        created = self.client.post(
            "/requests/new",
            data={"request_text": "Please revise the existing homepage hero during revision round two."},
        )
        self.assertEqual(created.status_code, 302)
        detail = self.client.get(created.location)
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Up to 5 responsive marketing pages.", detail.data)
        self.assertIn(b"Please revise the existing homepage hero", detail.data)
        self.assertIn(b"Analysis pipeline", detail.data)
        self.assertIn(b"Decision rules", detail.data)
        self.assertIn(b"Raw JSON", detail.data)
        self.assertNotIn(b"No rationale was captured", detail.data)
        self.assertIn(b"Human checkpoint", detail.data)

        request_id = created.location.rsplit("/", 1)[-1]
        denied = self.client.post(f"/requests/{request_id}/approve", data={})
        self.assertEqual(denied.status_code, 400)

        approved = self.client.post(
            f"/requests/{request_id}/approve",
            data={"review_acknowledged": "on"},
            follow_redirects=True,
        )
        self.assertEqual(approved.status_code, 200)
        self.assertIn(b"Approved locally", approved.data)
        self.assertEqual(self.store.list_records()[0].approval_status.value, "approved")

    def test_setup_form_clause_fields_match_the_sample_clause_fields(self) -> None:
        sample = evaluation_agreement()
        _, form = self._setup_form_project()
        sample_fields = sorted(
            (c.type.value, c.subtype, c.quantity, c.unit, c.concepts, c.qualifiers)
            for c in sample.clauses
        )
        form_fields = sorted(
            (c.type.value, c.subtype, c.quantity, c.unit, c.concepts, c.qualifiers)
            for c in form.clauses
        )
        self.assertEqual(form_fields, sample_fields)

    def test_setup_form_path_matches_sample_classifications_for_all_fixed_sets(self) -> None:
        cases = list(EVALUATION_CASES) + list(HOLDOUT_CASES) + list(FRESH_HOLDOUT_CASES)
        for case in cases:
            with self.subTest(case=case.id):
                sample_agreement = evaluation_agreement(case.agreement_variant)
                _, form_agreement = self._setup_form_project(case.agreement_variant)
                sample_result = analyze_request(
                    Request(id=f"sample-{case.id}", project_id="project-1", text=case.request_text),
                    sample_agreement,
                )
                form_result = analyze_request(
                    Request(id=f"form-{case.id}", project_id="project-1", text=case.request_text),
                    form_agreement,
                )
                self.assertEqual(form_result.classification, sample_result.classification)

    def test_setup_form_retrieval_excludes_unrelated_seo_metadata(self) -> None:
        _, form_agreement = self._setup_form_project()
        revision = analyze_request(
            "Can you do a 3rd round of changes on the pricing page.",
            form_agreement,
        )
        testimonials = analyze_request("Please add a testimonials page.", form_agreement)

        self.assertEqual(revision.classification.value, "POTENTIALLY_OUT_OF_SCOPE")
        self.assertNotIn("deliverables-2", revision.evidence_clause_ids)
        self.assertNotIn("deliverables-2", [hit.clause_id for hit in revision.trace.retrieve.hits])
        self.assertNotIn("deliverables-2", testimonials.evidence_clause_ids)
        self.assertNotIn("deliverables-2", [hit.clause_id for hit in testimonials.trace.retrieve.hits])

    def test_empty_request_is_rejected_before_persistence(self) -> None:
        response = self.client.post("/requests/new", data={"request_text": "   "})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.list_records(), [])

    def test_trace_humanizes_rule_labels_but_keeps_raw_identifiers_in_json(self) -> None:
        created = self.client.post(
            "/requests/new",
            data={"request_text": "Please add two case-study pages and design a new logo."},
        )
        detail = self.client.get(created.location)
        body = detail.get_data(as_text=True)

        self.assertIn("Quantity checked against current usage", body)
        self.assertIn("deliverable_quantity_is_checked_against_current_usage", body)
        self.assertIn("8 estimated hours", body)
        self.assertIn("$1,000", body)
        self.assertNotIn("8.0 hrs", body)

    def test_clarification_page_renders_concrete_questions(self) -> None:
        created = self.client.post(
            "/requests/new",
            data={"request_text": "Please improve SEO."},
        )
        detail = self.client.get(created.location)
        body = detail.get_data(as_text=True).lower()

        self.assertIn("metadata", body)
        self.assertIn("up to 5 pages", body)
        self.assertIn("strategy/keyword research", body)
        self.assertIn("excluded", body)

    def test_history_and_dashboard_rows_lead_with_request_text_and_mute_request_id(self) -> None:
        request_text = "Please add a testimonials page."
        created = self.client.post("/requests/new", data={"request_text": request_text})
        request_id = created.location.rsplit("/", 1)[-1]

        for path in ("/", "/history"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertIn(f"<strong>{request_text}</strong>", body)
            self.assertIn(f'<span class="request-id">{request_id}</span>', body)
