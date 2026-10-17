from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scopesentinel.domain import ApprovalStatus
from scopesentinel.store import JsonHistoryStore
from scopesentinel.web import create_app


class Step4BoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_path = Path(self.temp_dir.name) / "history.json"
        self.store = JsonHistoryStore(self.history_path)
        self.app = create_app(store=self.store)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_direct_approval_without_acknowledgment_is_400_and_stays_pending(self) -> None:
        created = self.client.post(
            "/requests/new",
            data={"request_text": "Please review the supplied homepage."},
        )
        self.assertEqual(created.status_code, 302)
        request_id = created.location.rsplit("/", 1)[-1]

        response = self.client.post(f"/requests/{request_id}/approve", data={})

        self.assertEqual(response.status_code, 400)
        records = self.store.list_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].approval_status, ApprovalStatus.PENDING_REVIEW)
        self.assertIsNone(records[0].approved_at)

    def test_empty_request_is_rejected_without_persistence(self) -> None:
        response = self.client.post("/requests/new", data={"request_text": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.list_records(), [])
        self.assertFalse(self.history_path.exists())

    def test_malformed_request_input_is_not_a_500_and_is_not_persisted(self) -> None:
        response = self.client.post(
            "/requests/new",
            data="{ definitely not valid form or JSON",
            content_type="application/json",
        )

        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.list_records(), [])
        self.assertFalse(self.history_path.exists())

    def test_corrupted_history_json_is_quarantined_and_visible_in_ui(self) -> None:
        self.history_path.write_text("{ not valid JSON", encoding="utf-8")

        self.assertEqual(self.store.list_records(), [])
        quarantined = list(self.history_path.parent.glob("history.corrupt-*.json"))
        self.assertEqual(len(quarantined), 1)
        self.assertFalse(self.history_path.exists())
        self.assertIn("Corrupted history was quarantined", self.client.get("/").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
