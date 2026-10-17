"""Frozen interfaces shared by the analysis engine, web app, and tests.

The engine will add behavior around these small data objects in later steps.
Keeping the objects serializable makes the pipeline trace and JSON history
portable without a database or an external service.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ClauseType(str, Enum):
    """The contract evidence categories understood by the MVP."""

    DELIVERABLE = "deliverable"
    EXCLUSION = "exclusion"
    LIMIT = "limit"
    RATE = "rate"
    DEADLINE = "deadline"


class Classification(str, Enum):
    """The only three classifications exposed to a user."""

    IN_SCOPE = "IN_SCOPE"
    POTENTIALLY_OUT_OF_SCOPE = "POTENTIALLY_OUT_OF_SCOPE"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


class ApprovalStatus(str, Enum):
    """Approval is deliberately separate from analysis classification."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"


@dataclass(frozen=True)
class Clause:
    """One source-preserving, typed agreement clause."""

    id: str
    type: ClauseType
    source_text: str
    subtype: str | None = None
    concepts: tuple[str, ...] = ()
    quantity: float | None = None
    unit: str | None = None
    qualifiers: tuple[str, ...] = ()


@dataclass
class Agreement:
    """The typed agreement plus project-specific usage and pricing inputs."""

    clauses: list[Clause] = field(default_factory=list)
    current_usage: dict[str, float] = field(default_factory=dict)
    pricing_rules: dict[str, Any] = field(default_factory=dict)


@dataclass
class Project:
    """A project whose requests are analyzed against one agreement."""

    id: str
    name: str
    client_name: str
    agreement: Agreement


@dataclass(frozen=True)
class Request:
    """The original client request submitted for analysis."""

    id: str
    project_id: str
    text: str


@dataclass
class ParseItem:
    """Normalized representation of one requested action."""

    item_id: str
    raw_text: str
    intent: str | None = None
    concepts: tuple[str, ...] = ()
    quantity: float | None = None
    unit: str | None = None
    qualifiers: tuple[str, ...] = ()
    unresolved_terms: tuple[str, ...] = ()
    ambiguity_tags: tuple[str, ...] = ()


@dataclass
class ParseOutput:
    """Visible output of the request parsing stage."""

    normalized_text: str = ""
    items: list[ParseItem] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)


@dataclass
class EvidenceHit:
    """One source-preserving clause returned by evidence retrieval."""

    clause_id: str
    clause_type: ClauseType
    source_text: str
    relation: str
    relevance_score: float = 0.0
    matched_concepts: tuple[str, ...] = ()
    matched_constraints: tuple[str, ...] = ()


@dataclass
class RetrieveOutput:
    """Visible output of the typed evidence retrieval stage."""

    hits: list[EvidenceHit] = field(default_factory=list)
    conflict_clause_ids: list[str] = field(default_factory=list)
    retrieval_notes: list[str] = field(default_factory=list)


@dataclass
class ClassifyOutput:
    """Visible output of the deterministic decision stage."""

    classification: Classification = Classification.NEEDS_CLARIFICATION
    rationale: list[str] = field(default_factory=list)
    evidence_clause_ids: list[str] = field(default_factory=list)
    uncertainty_tags: list[str] = field(default_factory=list)
    conflicting_clause_ids: list[str] = field(default_factory=list)
    scheduling_flag: str | None = None
    decision_rules: list[str] = field(default_factory=list)


@dataclass
class PipelineTrace:
    """Visible outputs from each deterministic analysis stage.

    These four fields are the integration boundary between the analysis agent
    and the web agent. Each stage must be populated and serializable.
    """

    parse: ParseOutput = field(default_factory=ParseOutput)
    retrieve: RetrieveOutput = field(default_factory=RetrieveOutput)
    classify: ClassifyOutput = field(default_factory=ClassifyOutput)
    draft: DraftAction | None = None


@dataclass
class DraftAction:
    """A proposed response or change order awaiting human review."""

    kind: str
    title: str
    body: str
    assumptions: list[str] = field(default_factory=list)
    estimated_hours: float | None = None
    estimated_cost: float | None = None
    estimate_label: str | None = None
    estimate_notes: list[str] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """A complete, evidence-backed analysis result."""

    request_id: str
    classification: Classification
    evidence_clause_ids: list[str] = field(default_factory=list)
    uncertainty_reasons: list[str] = field(default_factory=list)
    conflicting_clause_ids: list[str] = field(default_factory=list)
    scheduling_flag: str | None = None
    trace: PipelineTrace = field(default_factory=PipelineTrace)
    draft: DraftAction | None = None


@dataclass
class HistoryRecord:
    """Persisted request, analysis, and human approval state."""

    request: Request
    result: AnalysisResult
    approval_status: ApprovalStatus = ApprovalStatus.PENDING_REVIEW
    approved_at: str | None = None


def to_dict(value: Any) -> Any:
    """Convert domain objects into JSON-compatible primitives."""

    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_dict(item) for item in value]
    return value
