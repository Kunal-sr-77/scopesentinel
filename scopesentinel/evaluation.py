"""Fixed, labelled evaluation fixtures for the deterministic MVP engine.

This module is intentionally independent from the classifier implementation.
It freezes the expected behavior before implementation work begins. The
evaluation set includes the original worked examples A-E and adversarial cases
where a shared keyword is not enough to determine scope.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Agreement, Clause, ClauseType


@dataclass(frozen=True)
class EvaluationCase:
    """One labelled request and the evidence/uncertainty contract it tests."""

    id: str
    label: str
    request_text: str
    expected_classification: str
    expected_evidence_clause_ids: tuple[str, ...]
    expected_uncertainty_tags: tuple[str, ...]
    expected_scheduling_flag: str | None = None
    agreement_variant: str = "standard"


STANDARD_CLAUSES: tuple[Clause, ...] = (
    Clause(
        id="d-marketing-pages",
        type=ClauseType.DELIVERABLE,
        source_text="Up to 5 responsive marketing pages, including landing and case-study pages.",
        subtype="marketing_page",
        concepts=("marketing page", "landing page", "case-study page", "page"),
        quantity=5,
        unit="page",
    ),
    Clause(
        id="l-revision-rounds",
        type=ClauseType.LIMIT,
        source_text="Two revision rounds per page are included.",
        subtype="revision_round",
        concepts=("revision", "change", "edit"),
        quantity=2,
        unit="revision_round",
        qualifiers=("per page",),
    ),
    Clause(
        id="d-seo-metadata",
        type=ClauseType.DELIVERABLE,
        source_text="SEO metadata for up to 5 pages is included; SEO strategy is not included.",
        subtype="seo_metadata",
        concepts=("seo", "metadata", "meta title", "meta description"),
        quantity=5,
        unit="page",
    ),
    Clause(
        id="x-seo-strategy",
        type=ClauseType.EXCLUSION,
        source_text="SEO strategy, keyword research, and ranking guarantees are excluded.",
        subtype="seo_strategy",
        concepts=("seo", "strategy", "keyword research", "ranking"),
    ),
    Clause(
        id="x-logo-design",
        type=ClauseType.EXCLUSION,
        source_text="Logo design and brand identity work are excluded.",
        subtype="logo_design",
        concepts=("logo", "brand identity", "identity"),
    ),
    Clause(
        id="x-copywriting",
        type=ClauseType.EXCLUSION,
        source_text="Copywriting and creation of new marketing copy are excluded.",
        subtype="copywriting",
        concepts=("copywriting", "copy", "content writing", "write"),
    ),
    Clause(
        id="r-hourly-rate",
        type=ClauseType.RATE,
        source_text="Approved additional work is billed at $125 per hour.",
        subtype="hourly_rate",
        concepts=("additional work", "hourly", "rate"),
        quantity=125,
        unit="hour",
    ),
    Clause(
        id="r-page-effort",
        type=ClauseType.RATE,
        source_text="The explicit effort assumption for one additional marketing page is 4 hours.",
        subtype="effort_assumption",
        concepts=("additional marketing page", "page", "effort"),
        quantity=4,
        unit="hour",
    ),
    Clause(
        id="deadline-launch",
        type=ClauseType.DEADLINE,
        source_text="The agreed launch deadline is 30 November 2026.",
        subtype="launch_date",
        concepts=("launch", "deadline", "delivery date"),
        qualifiers=("2026-11-30",),
    ),
)


EVALUATION_CASES: tuple[EvaluationCase, ...] = (
    EvaluationCase(
        id="A",
        label="Worked example A: included revision",
        request_text="Please revise the existing homepage hero during revision round two.",
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages", "l-revision-rounds"),
        expected_uncertainty_tags=(),
    ),
    EvaluationCase(
        id="B",
        label="Worked example B: page limit and excluded logo",
        request_text="Please add two case-study pages and design a new logo.",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=(
            "d-marketing-pages",
            "x-logo-design",
            "r-hourly-rate",
            "r-page-effort",
        ),
        expected_uncertainty_tags=("logo_effort_assumption_missing",),
    ),
    EvaluationCase(
        id="C",
        label="Worked example C: vague premium and SEO request",
        request_text="Can you make the site feel more premium and improve SEO?",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-seo-metadata", "x-seo-strategy"),
        expected_uncertainty_tags=("design_intent_unspecified", "seo_meaning_ambiguous"),
    ),
    EvaluationCase(
        id="D",
        label="Worked example D: missing page quantity",
        request_text="Please add some landing pages.",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-marketing-pages",),
        expected_uncertainty_tags=("quantity_missing",),
    ),
    EvaluationCase(
        id="E",
        label="Worked example E: no effort assumption for estimate",
        request_text="Please add one additional marketing page.",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages", "r-hourly-rate"),
        expected_uncertainty_tags=("estimate_effort_assumption_missing",),
        agreement_variant="no_effort_assumption",
    ),
    EvaluationCase(
        id="F",
        label="Exactly within the revision allowance",
        request_text="Make one more revision to the homepage; this is revision round two.",
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages", "l-revision-rounds"),
        expected_uncertainty_tags=(),
    ),
    EvaluationCase(
        id="G",
        label="Revision allowance exceeded",
        request_text="Please do a third revision round on the homepage.",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages", "l-revision-rounds"),
        expected_uncertainty_tags=("revision_allowance_exceeded",),
    ),
    EvaluationCase(
        id="H",
        label="False positive: copy keyword is explicitly excluded",
        request_text="Please write the homepage copy for us.",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=("x-copywriting",),
        expected_uncertainty_tags=("excluded_work",),
    ),
    EvaluationCase(
        id="I",
        label="False positive: SEO keyword resolves to included metadata",
        request_text="Please add an SEO title and meta description to the homepage.",
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-seo-metadata",),
        expected_uncertainty_tags=(),
    ),
    EvaluationCase(
        id="J",
        label="False positive: SEO keyword remains ambiguous",
        request_text="Please improve our SEO rankings.",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-seo-metadata", "x-seo-strategy"),
        expected_uncertainty_tags=("seo_meaning_ambiguous",),
    ),
    EvaluationCase(
        id="K",
        label="No matching contractual evidence",
        request_text="Please build an e-commerce checkout and subscription billing flow.",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=(),
        expected_uncertainty_tags=("no_matching_clause",),
    ),
    EvaluationCase(
        id="L",
        label="Scheduling conflict is clarification, not out of scope",
        request_text="Can we launch the site on 15 November 2026 instead?",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("deadline-launch",),
        expected_uncertainty_tags=("scheduling_conflict",),
        expected_scheduling_flag="deadline_conflict",
    ),
    EvaluationCase(
        id="M",
        label="Scheduling request matches the agreed date",
        request_text="Please confirm launch for 30 November 2026.",
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("deadline-launch",),
        expected_uncertainty_tags=(),
    ),
    EvaluationCase(
        id="N",
        label="Page fits when current usage leaves capacity",
        request_text="Please add one marketing page.",
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages",),
        expected_uncertainty_tags=(),
        agreement_variant="four_pages_used",
    ),
    EvaluationCase(
        id="O",
        label="Additive page with unknown current usage",
        request_text="Please add one marketing page.",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-marketing-pages",),
        expected_uncertainty_tags=("current_usage_unknown",),
        agreement_variant="unknown_page_usage",
    ),
    EvaluationCase(
        id="P",
        label="Combined work with scheduling ambiguity",
        request_text="Add a new page and have the whole site launch on 15 November 2026.",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-marketing-pages", "deadline-launch"),
        expected_uncertainty_tags=("scheduling_conflict",),
        expected_scheduling_flag="deadline_conflict",
    ),
)


def evaluation_agreement(variant: str = "standard") -> Agreement:
    """Build the agreement variant named by an evaluation case."""

    clauses = list(STANDARD_CLAUSES)
    current_usage = {"marketing_page": 5, "revision_round:homepage": 1}
    pricing_rules = {
        "hourly_rate": 125,
        "effort_hours": {"additional_marketing_page": 4},
    }

    if variant == "no_effort_assumption":
        clauses = [clause for clause in clauses if clause.id != "r-page-effort"]
        pricing_rules = {"hourly_rate": 125, "effort_hours": {}}
    elif variant == "four_pages_used":
        current_usage["marketing_page"] = 4
    elif variant == "unknown_page_usage":
        current_usage.pop("marketing_page")
    elif variant != "standard":
        raise ValueError(f"Unknown evaluation agreement variant: {variant}")

    return Agreement(
        clauses=clauses,
        current_usage=current_usage,
        pricing_rules=pricing_rules,
    )
