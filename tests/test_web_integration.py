from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scopesentinel.store import JsonHistoryStore
from scopesentinel.web import create_app


class WebWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = JsonHistoryStore(Path(self.temp_dir.name) / "history.json")
        self.app = create_app(store=self.store)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

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
