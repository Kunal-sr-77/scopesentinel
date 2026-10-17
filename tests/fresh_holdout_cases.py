"""Fresh independent QA scenarios for the post-fix scope engine.

The cases use the existing agreement variants from
``scopesentinel.evaluation`` but deliberately use client language distinct
from the original evaluation and H01-H15 holdouts.  Expected values are
frozen here so the report can expose regressions without changing production
rules or the earlier fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass

from scopesentinel.evaluation import evaluation_agreement


@dataclass(frozen=True)
class FreshHoldoutCase:
    id: str
    label: str
    request_text: str
    expected_classification: str
    expected_evidence_clause_ids: tuple[str, ...]
    expected_uncertainty_tags: tuple[str, ...] = ()
    expected_scheduling_flag: str | None = None
    agreement_variant: str = "standard"
    false_positive_trap: bool = False
    check_estimate: bool = False
    expected_estimated_hours: float | None = None
    expected_estimated_cost: float | None = None
    expected_estimate_label: str | None = None


FRESH_HOLDOUT_CASES: tuple[FreshHoldoutCase, ...] = (
    FreshHoldoutCase(
        id="H16",
        label="Second revision is the inclusive boundary",
        request_text=(
            "The homepage hero needs its second revision; treat this as the final "
            "included round."
        ),
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages", "l-revision-rounds"),
    ),
    FreshHoldoutCase(
        id="H17",
        label="Third revision crosses the inclusive boundary",
        request_text="Please apply the third revision round to the homepage hero.",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages", "l-revision-rounds"),
        expected_uncertainty_tags=("revision_allowance_exceeded",),
    ),
    FreshHoldoutCase(
        id="H18",
        label="Supplied copy is preserved but its use is ambiguous",
        request_text=(
            "Add one landing page and copy the supplied wording onto it without "
            "writing new copy."
        ),
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-marketing-pages", "x-copywriting"),
        expected_uncertainty_tags=("copy_request_ambiguous",),
        agreement_variant="four_pages_used",
        false_positive_trap=True,
    ),
    FreshHoldoutCase(
        id="H19",
        label="An untouched existing logo does not make page work excluded",
        request_text=(
            "Create one case-study page while retaining the present logo exactly "
            "as it is."
        ),
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages",),
        agreement_variant="four_pages_used",
        false_positive_trap=True,
    ),
    FreshHoldoutCase(
        id="H20",
        label="Preserving the current design does not add an exclusion",
        request_text=(
            "Create one landing page while preserving the existing visual design."
        ),
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages",),
        agreement_variant="four_pages_used",
        false_positive_trap=True,
    ),
    FreshHoldoutCase(
        id="H21",
        label="Concrete metadata language selects the included SEO work",
        request_text="For the homepage, set only its meta title and meta description.",
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-seo-metadata",),
        false_positive_trap=True,
    ),
    FreshHoldoutCase(
        id="H22",
        label="SEO strategy wording remains ambiguous",
        request_text="Handle the site's SEO for search rankings and keyword direction.",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-seo-metadata", "x-seo-strategy"),
        expected_uncertainty_tags=("seo_meaning_ambiguous",),
    ),
    FreshHoldoutCase(
        id="H23",
        label="Numeric page quantity receives a supported estimate",
        request_text="Create three case-study pages and include an estimate.",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=(
            "d-marketing-pages",
            "r-hourly-rate",
            "r-page-effort",
        ),
        check_estimate=True,
        expected_estimated_hours=12,
        expected_estimated_cost=1500,
        expected_estimate_label=(
            "Estimate: 3 pages × 4 hours/page = 12 estimated hours; 12 hours × "
            "$125/hour = $1,500."
        ),
    ),
    FreshHoldoutCase(
        id="H24",
        label="Several pages still need a concrete quantity",
        request_text="We would like several landing pages for the campaign.",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-marketing-pages",),
        expected_uncertainty_tags=("quantity_missing",),
    ),
    FreshHoldoutCase(
        id="H25",
        label="Mixed page and logo work keeps a partial estimate despite a date conflict",
        request_text=(
            "Create two additional case-study pages and design a fresh logo, then "
            "launch the site on 15 November 2026; include a quote."
        ),
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=(
            "d-marketing-pages",
            "x-logo-design",
            "r-hourly-rate",
            "r-page-effort",
            "deadline-launch",
        ),
        expected_uncertainty_tags=(
            "scheduling_conflict",
            "logo_effort_assumption_missing",
        ),
        expected_scheduling_flag="deadline_conflict",
        check_estimate=True,
        expected_estimated_hours=8,
        expected_estimated_cost=1000,
        expected_estimate_label=(
            "Estimate: 2 pages × 4 hours/page = 8 estimated hours; 8 hours × "
            "$125/hour = $1,000. Logo is not included in the estimate because no "
            "explicit logo effort assumption is configured."
        ),
    ),
)


def agreement_for(case: FreshHoldoutCase):
    """Return the existing evaluation agreement variant for one case."""

    return evaluation_agreement(case.agreement_variant)
