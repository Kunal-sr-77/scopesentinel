"""Small atomic JSON persistence adapter."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from dataclasses import fields
from pathlib import Path
from typing import Any

from .domain import (
    AnalysisResult,
    ApprovalStatus,
    ClassifyOutput,
    ClauseType,
    Classification,
    DraftAction,
    EvidenceHit,
    HistoryRecord,
    ParseItem,
    ParseOutput,
    PipelineTrace,
    Request,
    RetrieveOutput,
    to_dict,
)


class JsonHistoryStore:
    """Persist history without a database or native dependency."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.last_notice: str | None = None

    def list_records(self) -> list[HistoryRecord]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            corrupt_path = self.path.with_name(
                f"{self.path.stem}.corrupt-{timestamp}{self.path.suffix}"
            )
            os.replace(self.path, corrupt_path)
            self.last_notice = (
                f"Corrupted history was quarantined as {corrupt_path.name}. "
                "Starting with empty history."
            )
            return []
        return [_record_from_dict(item) for item in payload]

    def save(self, record: HistoryRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        records = self.list_records()
        records = [item for item in records if item.request.id != record.request.id]
        records.append(record)
        serialized = json.dumps([to_dict(item) for item in records], indent=2)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, self.path)


def _record_from_dict(payload: dict[str, Any]) -> HistoryRecord:
    request_data = payload["request"]
    result_data = payload["result"]
    draft_data = result_data.get("draft")
    trace_data = result_data.get("trace", {})
    draft = DraftAction(**draft_data) if draft_data else None
    result = AnalysisResult(
        request_id=result_data["request_id"],
        classification=Classification(result_data["classification"]),
        evidence_clause_ids=result_data.get("evidence_clause_ids", []),
        uncertainty_reasons=result_data.get("uncertainty_reasons", []),
        conflicting_clause_ids=result_data.get("conflicting_clause_ids", []),
        scheduling_flag=result_data.get("scheduling_flag"),
        trace=_pipeline_from_dict(trace_data),
        draft=draft,
    )
    return HistoryRecord(
        request=Request(**request_data),
        result=result,
        approval_status=ApprovalStatus(payload.get("approval_status", ApprovalStatus.PENDING_REVIEW.value)),
        approved_at=payload.get("approved_at"),
    )


def _pipeline_from_dict(payload: dict[str, Any]) -> PipelineTrace:
    parse_data = payload.get("parse", {})
    retrieve_data = payload.get("retrieve", {})
    classify_data = payload.get("classify", {})
    parse = ParseOutput(
        normalized_text=parse_data.get("normalized_text", ""),
        items=[ParseItem(**item) for item in parse_data.get("items", [])],
        missing_information=parse_data.get("missing_information", []),
    )
    retrieve = RetrieveOutput(
        hits=[
            EvidenceHit(
                **{
                    **item,
                    "clause_type": ClauseType(item["clause_type"]),
                }
            )
            for item in retrieve_data.get("hits", [])
        ],
        conflict_clause_ids=retrieve_data.get("conflict_clause_ids", []),
        retrieval_notes=retrieve_data.get("retrieval_notes", []),
    )
    classify = ClassifyOutput(
        classification=Classification(
            classify_data.get("classification", Classification.NEEDS_CLARIFICATION.value)
        ),
        rationale=classify_data.get("rationale", []),
        evidence_clause_ids=classify_data.get("evidence_clause_ids", []),
        uncertainty_tags=classify_data.get("uncertainty_tags", []),
        conflicting_clause_ids=classify_data.get("conflicting_clause_ids", []),
        scheduling_flag=classify_data.get("scheduling_flag"),
        decision_rules=classify_data.get("decision_rules", []),
    )
    draft_data = payload.get("draft")
    draft = DraftAction(**draft_data) if draft_data else None
    return PipelineTrace(parse=parse, retrieve=retrieve, classify=classify, draft=draft)
