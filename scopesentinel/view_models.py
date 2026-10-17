"""Stable browser-facing view-model interfaces.

Routes may adapt domain objects into these models, but templates and browser
scripts should consume only these fields. The frontend agent owns presentation;
the main agent owns construction of these models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .domain import ApprovalStatus, Classification, DraftAction


@dataclass(frozen=True)
class EvidenceViewModel:
    clause_id: str
    clause_type: str
    source_text: str
    relation: str
    matched_concepts: tuple[str, ...] = ()
    matched_constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class PipelineStageViewModel:
    key: str
    label: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisViewModel:
    request_id: str
    project_name: str
    client_request: str
    request_heading: str
    classification: Classification
    classification_label: str
    rationale: tuple[str, ...] = ()
    decision_rules: tuple[str, ...] = ()
    uncertainty_tags: tuple[str, ...] = ()
    scheduling_flag: str | None = None
    evidence: tuple[EvidenceViewModel, ...] = ()
    draft: DraftAction | None = None
    pipeline: tuple[PipelineStageViewModel, ...] = ()
    approval_status: ApprovalStatus = ApprovalStatus.PENDING_REVIEW
    can_approve: bool = False


@dataclass(frozen=True)
class DashboardViewModel:
    project_name: str
    client_name: str
    pending_review_count: int
    history: tuple[AnalysisViewModel, ...] = ()
