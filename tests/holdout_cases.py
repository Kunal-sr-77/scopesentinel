"""Independent Step 4 holdout cases.

These cases deliberately live under ``tests`` and do not extend the original
16-case fixture in :mod:`scopesentinel.evaluation`.  The wording is client
style, while the labels freeze the QA oracle used by ``test_holdout.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from scopesentinel.evaluation import evaluation_agreement


@dataclass(frozen=True)
class HoldoutCase:
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


HOLDOUT_CASES: tuple[HoldoutCase, ...] = (
    HoldoutCase(
        id="H01",
        label="Included landing page uses the remaining allowance",
        request_text="Could you add one landing page for the campaign?",
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages",),
        agreement_variant="four_pages_used",
    ),
    HoldoutCase(
        id="H02",
        label="Final included homepage revision",
        request_text="Please make the second and final revision to the homepage hero.",
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages", "l-revision-rounds"),
    ),
    HoldoutCase(
        id="H03",
        label="Fourth edit exceeds the revision limit",
        request_text="We need a fourth round of edits on the landing page.",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages", "l-revision-rounds"),
        expected_uncertainty_tags=("revision_allowance_exceeded",),
    ),
    HoldoutCase(
        id="H04",
        label="Additional case-study pages exceed page capacity",
        request_text="Could you add two new case-study pages to the site?",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=(
            "d-marketing-pages",
            "r-hourly-rate",
            "r-page-effort",
        ),
    ),
    HoldoutCase(
        id="H05",
        label="Logo request matches an explicit exclusion",
        request_text="The brand team wants a fresh logo mark for the website.",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=(
            "x-logo-design",
            "r-hourly-rate",
            "r-page-effort",
        ),
        expected_uncertainty_tags=("logo_effort_assumption_missing",),
    ),
    HoldoutCase(
        id="H06",
        label="Copy can mean reusing supplied wording rather than writing",
        request_text=(
            "Could you copy the existing homepage wording onto the case-study page, "
            "without writing new copy?"
        ),
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-marketing-pages", "x-copywriting"),
        expected_uncertainty_tags=("copy_request_ambiguous",),
        false_positive_trap=True,
    ),
    HoldoutCase(
        id="H07",
        label="SEO keyword is narrowed to included page metadata",
        request_text=(
            "When you say SEO, I mean the page title and description tags for the "
            "landing page."
        ),
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-seo-metadata",),
        false_positive_trap=True,
    ),
    HoldoutCase(
        id="H08",
        label="Vague quantity needs a number",
        request_text="We'd love a few more landing pages before the campaign.",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-marketing-pages",),
        expected_uncertainty_tags=("quantity_missing",),
    ),
    HoldoutCase(
        id="H09",
        label="Unsupported portal and billing request has no evidence",
        request_text="Can you add a customer portal with account sign-in and recurring billing?",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=(),
        expected_uncertainty_tags=("no_matching_clause",),
    ),
    HoldoutCase(
        id="H10",
        label="Requested launch date matches the agreement",
        request_text="Could we keep the launch on 30 November 2026?",
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("deadline-launch",),
    ),
    HoldoutCase(
        id="H11",
        label="Earlier launch date is a scheduling conflict",
        request_text="The client is asking to launch on 15 November 2026.",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("deadline-launch",),
        expected_uncertainty_tags=("scheduling_conflict",),
        expected_scheduling_flag="deadline_conflict",
    ),
    HoldoutCase(
        id="H12",
        label="Extra page estimate lacks an effort assumption",
        request_text="Please add one extra marketing page and quote the work.",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages", "r-hourly-rate"),
        expected_uncertainty_tags=("estimate_effort_assumption_missing",),
        agreement_variant="no_effort_assumption",
        check_estimate=True,
    ),
    HoldoutCase(
        id="H13",
        label="Two extra pages have a supported estimate",
        request_text="Can you add two new marketing pages and send an estimate?",
        expected_classification="POTENTIALLY_OUT_OF_SCOPE",
        expected_evidence_clause_ids=(
            "d-marketing-pages",
            "r-hourly-rate",
            "r-page-effort",
        ),
        check_estimate=True,
        expected_estimated_hours=8,
        expected_estimated_cost=1000,
    ),
    HoldoutCase(
        id="H14",
        label="Mentioning an unchanged logo must not exclude page work",
        request_text="Please add one landing page; leave the existing logo exactly as it is.",
        expected_classification="IN_SCOPE",
        expected_evidence_clause_ids=("d-marketing-pages",),
        agreement_variant="four_pages_used",
        false_positive_trap=True,
    ),
    HoldoutCase(
        id="H15",
        label="Premium homepage wording remains underspecified",
        request_text="Please make the homepage feel more premium, and keep all copy exactly as supplied.",
        expected_classification="NEEDS_CLARIFICATION",
        expected_evidence_clause_ids=("d-marketing-pages", "x-copywriting"),
        expected_uncertainty_tags=("design_intent_unspecified",),
        false_positive_trap=True,
    ),
)


def agreement_for(case: HoldoutCase):
    """Return a fresh agreement for one holdout case."""

    return evaluation_agreement(case.agreement_variant)
