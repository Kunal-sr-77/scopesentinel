from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scopesentinel.domain import (
    Agreement,
    AnalysisResult,
    Classification,
    Clause,
    ClauseType,
    HistoryRecord,
    Project,
    Request,
    to_dict,
)
from scopesentinel.store import JsonHistoryStore
from scopesentinel.web import create_app


class SkeletonTests(unittest.TestCase):
    def test_frozen_domain_interfaces_are_json_serializable(self) -> None:
        clause = Clause(
            id="deliverable-1",
            type=ClauseType.DELIVERABLE,
            source_text="Up to 5 responsive marketing pages",
            subtype="page",
            concepts=("marketing", "page"),
            quantity=5,
            unit="page",
        )
        project = Project(
            id="project-1",
            name="Northstar",
            client_name="Northstar",
            agreement=Agreement(clauses=[clause], current_usage={"page": 2}),
        )
        payload = to_dict(project)
        self.assertEqual(payload["agreement"]["clauses"][0]["source_text"], clause.source_text)
        json.dumps(payload)

    def test_history_store_round_trips_through_a_temporary_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "history.json"
            record = HistoryRecord(
                request=Request(id="request-1", project_id="project-1", text="Please review this."),
                result=AnalysisResult(
                    request_id="request-1",
                    classification=Classification.NEEDS_CLARIFICATION,
                    uncertainty_reasons=["No concrete deliverable identified."],
                ),
            )
            store = JsonHistoryStore(history_path)
            store.save(record)
            loaded = store.list_records()

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].request.id, "request-1")
        self.assertEqual(loaded[0].result.classification, Classification.NEEDS_CLARIFICATION)
        self.assertFalse(Path("data/history.json").exists())

    def test_health_endpoint_is_local_and_deterministic(self) -> None:
        client = create_app().test_client()
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "service": "scopesentinel"})
