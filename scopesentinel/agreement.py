"""Deterministic agreement-clause parsing helpers.

The parser is deliberately small: agreements may also be supplied as already
typed :class:`~scopesentinel.domain.Clause` objects (as the evaluation set
does).  Text parsing exists for the local MVP and never changes the source
text that is shown as evidence.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .domain import Agreement, Clause, ClauseType


_NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
}

_CONCEPT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("marketing page", ("marketing page", "web page", "pages", "page")),
    ("landing page", ("landing page", "landing pages")),
    ("case-study page", ("case-study page", "case-study pages", "case study page", "case study pages")),
    ("seo metadata", ("seo metadata", "meta title", "meta description", "metadata")),
    ("seo strategy", ("seo strategy", "keyword research", "ranking")),
    ("seo", ("seo",)),
    ("logo", ("logo",)),
    ("brand identity", ("brand identity", "identity")),
    ("copywriting", ("copywriting", "marketing copy", "content writing", "copy")),
    ("revision", ("revision", "change", "edit")),
    ("additional work", ("additional work",)),
    ("hourly rate", ("hourly", "rate", "billed")),
    ("effort assumption", ("effort assumption", "effort")),
    ("launch", ("launch", "deadline", "delivery date")),
)


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _number_in(text: str) -> float | None:
    text = text.lower()
    match = re.search(r"(?<![\w$])\d+(?:\.\d+)?", text)
    if match:
        return float(match.group())
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            return float(value)
    return None


def _display_number(value: float | None) -> float | None:
    if value is None:
        return None
    return int(value) if value.is_integer() else value


def _concepts(text: str) -> tuple[str, ...]:
    lowered = _normalized(text)
    result: list[str] = []
    for concept, patterns in _CONCEPT_PATTERNS:
        if any(re.search(rf"\b{re.escape(pattern)}\b", lowered) for pattern in patterns):
            if concept not in result:
                result.append(concept)
    return tuple(result)


def _clause_type(text: str) -> ClauseType:
    lowered = _normalized(text)
    if re.search(r"\b(excluded|exclusion|out of scope|not covered)\b", lowered):
        return ClauseType.EXCLUSION
    not_included = re.search(r"\bnot included\b", lowered)
    included = re.search(r"\bincluded\b", lowered)
    if not_included and not (included and included.start() < not_included.start()):
        return ClauseType.EXCLUSION
    if re.search(r"\b(deadline|launch date|delivery date|launch on)\b", lowered):
        return ClauseType.DEADLINE
    if re.search(r"\b(\$\s*\d|per hour|hourly|billed|effort assumption)\b", lowered):
        return ClauseType.RATE
    if re.search(r"\b(revision|maximum|limit|no more than)\b", lowered):
        return ClauseType.LIMIT
    return ClauseType.DELIVERABLE


def _subtype(clause_type: ClauseType, concepts: tuple[str, ...], text: str) -> str | None:
    lowered = _normalized(text)
    if clause_type is ClauseType.DEADLINE:
        return "launch_date"
    if clause_type is ClauseType.RATE:
        if "effort assumption" in concepts:
            return "effort_assumption"
        if "hourly rate" in concepts or "per hour" in lowered:
            return "hourly_rate"
    if clause_type is ClauseType.LIMIT and "revision" in concepts:
        return "revision_round"
    if clause_type is ClauseType.EXCLUSION and "logo" in concepts:
        return "logo_design"
    for candidate in (
        "seo metadata",
        "seo strategy",
        "logo",
        "copywriting",
        "marketing page",
    ):
        if candidate in concepts:
            return candidate.replace(" ", "_").replace("-", "_")
    return concepts[0].replace(" ", "_").replace("-", "_") if concepts else None


def _unit(clause_type: ClauseType, subtype: str | None, text: str) -> str | None:
    lowered = _normalized(text)
    if clause_type is ClauseType.RATE and "per hour" in lowered:
        return "hour"
    if subtype == "effort_assumption":
        return "hour"
    if subtype == "revision_round" or "revision round" in lowered:
        return "revision_round"
    if re.search(r"\b(page|pages)\b", lowered):
        return "page"
    if re.search(r"\b(hour|hours)\b", lowered):
        return "hour"
    return None


def _qualifiers(text: str) -> tuple[str, ...]:
    lowered = _normalized(text)
    qualifiers: list[str] = []
    if re.search(r"\bper page\b", lowered):
        qualifiers.append("per page")
    date = re.search(r"\b(\d{1,2})\s+([a-z]+)\s+(\d{4})\b", lowered)
    if date:
        months = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }
        month = months.get(date.group(2))
        if month:
            qualifiers.append(f"{date.group(3)}-{month:02d}-{int(date.group(1)):02d}")
    return tuple(qualifiers)


def parse_clause(
    source_text: str,
    clause_id: str | None = None,
    clause_type: ClauseType | None = None,
) -> Clause:
    """Parse one clause while retaining its exact source string."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise ValueError("source_text must be a non-empty string")
    source = source_text
    clause_type = clause_type or _clause_type(source)
    concepts = _concepts(source)
    if "seo metadata" in concepts or "seo strategy" in concepts:
        concepts = tuple(
            concept
            for concept in concepts
            if concept not in {"marketing page", "landing page", "case-study page"}
        )
    subtype = _subtype(clause_type, concepts, source)
    quantity = _display_number(_number_in(source))
    if clause_type is ClauseType.RATE and subtype == "hourly_rate":
        dollar = re.search(r"\$\s*(\d+(?:\.\d+)?)", source)
        quantity = float(dollar.group(1)) if dollar else quantity
        quantity = _display_number(quantity)
    if subtype == "marketing_page":
        concepts = ("marketing page", "landing page", "case-study page", "page")
    elif subtype == "revision_round":
        concepts = ("revision", "change", "edit")
    elif subtype == "seo_metadata":
        concepts = ("seo", "metadata", "meta title", "meta description")
    elif subtype == "seo_strategy":
        concepts = ("seo", "strategy", "keyword research", "ranking")
    elif subtype == "logo_design":
        concepts = ("logo", "brand identity", "identity")
    elif subtype == "copywriting":
        concepts = ("copywriting", "copy", "content writing", "write")
    elif subtype == "hourly_rate":
        concepts = ("additional work", "hourly", "rate")
    elif subtype == "effort_assumption":
        concepts = ("additional marketing page", "page", "effort")
    if subtype == "launch_date":
        quantity = None
        concepts = ("launch", "deadline", "delivery date")
    generated_id = clause_id or f"{clause_type.value}-{len(source)}"
    return Clause(
        id=generated_id,
        type=clause_type,
        source_text=source,
        subtype=subtype,
        concepts=concepts,
        quantity=quantity,
        unit=_unit(clause_type, subtype, source),
        qualifiers=_qualifiers(source),
    )


def _source_clauses(text: str) -> list[str]:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def parse_agreement(
    source: str | Iterable[Clause],
    *,
    current_usage: dict[str, float] | None = None,
    pricing_rules: dict[str, object] | None = None,
) -> Agreement:
    """Build an agreement from clauses or one clause-per-line source text."""

    if isinstance(source, str):
        clauses = [
            parse_clause(clause_text, clause_id=f"clause-{index}")
            for index, clause_text in enumerate(_source_clauses(source), start=1)
        ]
    else:
        clauses = list(source)
    return Agreement(
        clauses=clauses,
        current_usage=dict(current_usage or {}),
        pricing_rules=dict(pricing_rules or {}),
    )


parse_contract = parse_agreement
