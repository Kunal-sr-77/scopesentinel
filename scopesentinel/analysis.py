"""Local deterministic request analysis pipeline."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from .domain import (
    Agreement,
    AnalysisResult,
    Clause,
    ClauseType,
    ClassifyOutput,
    Classification,
    DraftAction,
    EvidenceHit,
    ParseItem,
    ParseOutput,
    PipelineTrace,
    Project,
    Request,
    RetrieveOutput,
)


_NUMBER_WORDS = {
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
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}

_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("marketing page", ("marketing page", "landing page", "case-study page", "case study page", "homepage", "web page", "page")),
    ("landing page", ("landing page",)),
    ("case-study page", ("case-study page", "case study page")),
    ("seo metadata", ("seo title", "meta title", "meta description", "seo metadata", "metadata")),
    ("seo", ("seo",)),
    ("seo strategy", ("seo strategy", "keyword research", "seo ranking", "seo rankings", "ranking")),
    ("logo", ("logo",)),
    ("brand identity", ("brand identity", "identity")),
    ("copywriting", ("copywriting", "copy", "marketing copy", "content writing", "write")),
    ("revision", ("revision", "revise", "edit", "change", "tweak", "round of changes", "round of edits", "round of tweaks")),
    ("launch", ("launch", "deadline", "delivery date")),
    ("design", ("design", "premium", "look and feel")),
)


def _lower(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _number(text: str) -> float | None:
    match = re.search(r"(?<!\w)\d+(?:\.\d+)?", text)
    if match:
        return float(match.group())
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", text):
            return float(value)
    return None


def _number_value(value: float | None) -> float | None:
    if value is None:
        return None
    return int(value) if value.is_integer() else value


def _unit(text: str, concepts: tuple[str, ...]) -> str | None:
    if "revision" in concepts or re.search(r"\b(round|rounds)\b", text):
        return "revision_round"
    if "marketing page" in concepts or "landing page" in concepts or "case-study page" in concepts:
        return "page"
    if re.search(r"\b(hours?|hrs?)\b", text):
        return "hour"
    return None


def _concepts(text: str) -> tuple[str, ...]:
    result: list[str] = []
    for concept, aliases in _ALIASES:
        if any(alias in text for alias in aliases) and concept not in result:
            result.append(concept)
    stop_words = {
        "please", "can", "you", "the", "this", "that", "for", "from", "with", "without",
        "and", "our", "site", "feel", "more", "make", "add", "build", "create", "provide",
        "write", "design", "have", "whole", "instead", "new", "existing", "one", "two", "three",
        "case", "study", "pages", "page", "improve", "few", "several",
    }
    for word in re.findall(r"[a-z]+", text):
        if len(word) > 3 and word not in stop_words and word not in result:
            result.append(word)
    return tuple(result)


def _qualifiers(text: str) -> tuple[str, ...]:
    qualifiers: list[str] = []
    for pattern, value in (
        (r"\b(existing|new|whole site)\b", None),
        (r"\bfor ([a-z][a-z -]+?)(?=\s*(?:,|\band\b|$))", "group"),
        (r"\b(during revision round (?:\w+|\d+))\b", None),
        (r"\bwithout ([a-z][a-z ]+?)(?=\s*(?:,|$))", None),
    ):
        for match in re.finditer(pattern, text):
            qualifiers.append(match.group(1).strip() if value == "group" else match.group(0).strip())
    return tuple(dict.fromkeys(qualifiers))


def _unresolved_terms(text: str) -> tuple[str, ...]:
    terms = []
    for term in ("some", "premium", "better", "more", "appropriate", "etc"):
        if re.search(rf"\b{re.escape(term)}\b", text):
            terms.append(term)
    return tuple(terms)


def _copy_request_is_ambiguous(text: str, concepts: tuple[str, ...]) -> bool:
    return "copywriting" in concepts and bool(
        re.search(r"\bcopy\b.*\b(?:onto|to)\b", text)
        and re.search(r"\b(existing|supplied|provided|current)\b|without writing", text)
    )


def _preserves_existing(text: str, subject: str) -> bool:
    if not re.search(rf"\b{re.escape(subject)}\b", text):
        return False
    return bool(
        re.search(
            rf"\b(?:keep|leave|retain|preserve|unchanged)\b.*\b{re.escape(subject)}\b|"
            rf"\b{re.escape(subject)}\b.*\b(?:unchanged|exactly as (?:is|it is)|without changing)\b",
            text,
        )
    )


def _request_quantity(text: str) -> float | None:
    quantity_words = "\\d+|one|two|three|four|five|six|seven|eight|nine|ten"
    page_descriptor = r"(?!(?:few|several|some|couple|more)\b)(?:[a-z][a-z-]*\s+)?"
    page_pattern = (
        rf"\b({quantity_words})\s+(?:new\s+|additional\s+|extra\s+|more\s+)?"
        rf"{page_descriptor}pages?\b"
    )
    match = re.search(page_pattern, text)
    if match:
        return _number_value(_number(match.group(1)))
    article_match = re.search(
        r"\b(an?|one)\s+(?:new\s+|additional\s+|extra\s+)?"
        rf"{page_descriptor}pages?\b",
        text,
    )
    return 1 if article_match else None


def _vague_page_quantity(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:a few|few|several|a couple|couple|some|more)\s+"
            r"(?:new\s+|additional\s+)?(?:(?:marketing|landing|case[- ]study)\s+)?pages?\b",
            text,
        )
    )


def _explicit_metadata_language(text: str) -> bool:
    return any(
        term in text
        for term in ("seo title", "meta title", "meta description", "metadata", "seo metadata")
    ) or bool(
        re.search(r"\b(?:page )?title\b.*\bdescription tags?\b|\bdescription tags?\b", text)
    )


def _ambiguity_tags(text: str, concepts: tuple[str, ...], quantity: float | None) -> tuple[str, ...]:
    tags: list[str] = []
    if "premium" in text or "look and feel" in text:
        tags.append("design_intent_unspecified")
    if "seo" in concepts and not any(
        phrase in text for phrase in ("seo title", "meta title", "meta description", "metadata", "seo metadata")
    ) and not _explicit_metadata_language(text):
        tags.append("seo_meaning_ambiguous")
    page_request = "marketing page" in concepts or "landing page" in concepts or "case-study page" in concepts
    if page_request and quantity is None and _vague_page_quantity(text):
        tags.append("quantity_missing")
    if _copy_request_is_ambiguous(text, concepts):
        tags.append("copy_request_ambiguous")
    return tuple(tags)


def _split_request(text: str) -> list[str]:
    # Split only where the next fragment starts a new action. This keeps
    # "SEO title and meta description" as one requested item.
    pattern = r"(?:,\s*|\s+)and\s+(?=(?:add|design|build|create|write|revise|make|improve|update|have|confirm|launch)\b)"
    parts = [part.strip(" ,") for part in re.split(pattern, text, flags=re.IGNORECASE)]
    return [part for part in parts if part]


def _intent(text: str) -> str | None:
    if re.search(r"\b(revise|revision|edit|change|tweak|update)\b", text) or re.search(
        r"\b(?:\d+(?:st|nd|rd|th)|one|two|three|four|five)\s+round\s+of\s+(?:changes|edits|tweaks)\b",
        text,
    ):
        return "revise"
    if re.search(r"\b(add|create|build|design|write)\b", text):
        return "add"
    if re.search(r"\b(improve|make|enhance)\b", text):
        return "improve"
    if re.search(r"\b(launch|confirm)\b", text):
        return "schedule"
    return None


def parse_request(text: str) -> ParseOutput:
    """Parse an untrusted request into normalized, typed request items."""

    if not isinstance(text, str) or not text.strip():
        return ParseOutput()
    normalized = _lower(text)
    items: list[ParseItem] = []
    missing: list[str] = []
    for index, raw in enumerate(_split_request(normalized), start=1):
        concepts = _concepts(raw)
        quantity = None if "launch" in concepts else _request_quantity(raw)
        tags = _ambiguity_tags(raw, concepts, quantity)
        item = ParseItem(
            item_id=f"item-{index}",
            raw_text=raw,
            intent=_intent(raw),
            concepts=concepts,
            quantity=quantity,
            unit=_unit(raw, concepts),
            qualifiers=_qualifiers(raw),
            unresolved_terms=_unresolved_terms(raw),
            ambiguity_tags=tags,
        )
        items.append(item)
        for tag in tags:
            if tag not in missing:
                missing.append(tag)
    return ParseOutput(normalized_text=normalized, items=items, missing_information=missing)


def _canonical(value: str) -> str:
    value = value.lower().replace("-", " ")
    for concept, aliases in _ALIASES:
        if value == concept or value in aliases:
            return concept
    return value


def _concept_match(item: ParseItem, clause: Clause) -> tuple[str, ...]:
    item_concepts = {_canonical(concept) for concept in item.concepts}
    clause_concepts = {_canonical(concept) for concept in clause.concepts}
    matched = item_concepts & clause_concepts
    return tuple(sorted(matched))


def _hit(clause: Clause, relation: str, matched: tuple[str, ...], constraints: Iterable[str] = ()) -> EvidenceHit:
    return EvidenceHit(
        clause_id=clause.id,
        clause_type=clause.type,
        source_text=clause.source_text,
        relation=relation,
        relevance_score=1.0 if relation != "context" else 0.5,
        matched_concepts=matched,
        matched_constraints=tuple(constraints),
    )


def _date_in(text: str) -> str | None:
    match = re.search(r"\b(\d{1,2})\s+([a-z]+)\s+(\d{4})\b", text.lower())
    if not match:
        return None
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
    month = months.get(match.group(2))
    return f"{match.group(3)}-{month:02d}-{int(match.group(1)):02d}" if month else None


def _is_page_item(item: ParseItem) -> bool:
    return bool({"marketing page", "landing page", "case-study page"} & set(item.concepts))


def _explicit_page_request(item: ParseItem) -> bool:
    if "seo metadata" in item.concepts or "copywriting" in item.concepts:
        return bool(re.search(r"\b(page|pages|landing|case[- ]study)\b", item.raw_text))
    return bool(re.search(r"\b(page|pages|landing|homepage|case[- ]study)\b", item.raw_text))


def _page_deliverable(agreement: Agreement) -> Clause | None:
    return next(
        (
            clause
            for clause in agreement.clauses
            if clause.type is ClauseType.DELIVERABLE
            and (
                clause.subtype in {"marketing_page", "page"}
                or "marketing page" in {_canonical(concept) for concept in clause.concepts}
            )
        ),
        None,
    )


def _page_usage(agreement: Agreement) -> float | None:
    if "marketing_page" in agreement.current_usage:
        return agreement.current_usage["marketing_page"]
    return agreement.current_usage.get("page")


def _has_explicit_metadata(item: ParseItem) -> bool:
    return _explicit_metadata_language(item.raw_text)


def retrieve_evidence(parsed: ParseOutput | str, agreement: Agreement) -> RetrieveOutput:
    """Retrieve typed source clauses without making a scope decision."""

    if isinstance(parsed, str):
        parsed = parse_request(parsed)

    item_matches: dict[str, set[str]] = {}
    hits_by_id: dict[str, EvidenceHit] = {}
    for item in parsed.items:
        matched_ids: set[str] = set()
        for clause in agreement.clauses:
            if clause.type is ClauseType.RATE:
                continue
            if (
                clause.type is ClauseType.DELIVERABLE
                and clause.subtype == "marketing_page"
                and "copywriting" in item.concepts
                and item.intent == "add"
                and not re.search(r"\b(page|pages|landing|case[- ]study)\b", item.raw_text)
            ):
                continue
            if (
                clause.type is ClauseType.DELIVERABLE
                and clause.subtype == "marketing_page"
                and _has_explicit_metadata(item)
            ):
                continue
            concepts = _concept_match(item, clause)
            if not concepts:
                continue
            if clause.type is ClauseType.DELIVERABLE and "seo" in item.concepts and not _has_explicit_metadata(item):
                if "seo strategy" not in clause.concepts and "seo metadata" not in clause.concepts and "seo" not in clause.concepts:
                    continue
            if clause.type is ClauseType.EXCLUSION and "seo" in item.concepts and _has_explicit_metadata(item):
                continue
            preserved_logo = clause.subtype == "logo_design" and _preserves_existing(item.raw_text, "logo")
            relation = "context" if preserved_logo else (
                "excludes" if clause.type is ClauseType.EXCLUSION else "supports"
            )
            if clause.type is ClauseType.LIMIT:
                relation = "limits"
            constraints = ("preservation",) if preserved_logo else ()
            hit = _hit(clause, relation, concepts, constraints)
            matched_ids.add(clause.id)
            hits_by_id.setdefault(clause.id, hit)
        item_matches[item.item_id] = matched_ids

        if (
            _is_page_item(item)
            and _explicit_page_request(item)
            and re.search(r"\b(add|create|build)\b", item.raw_text)
            and not any("launch" in candidate.concepts for candidate in parsed.items)
        ):
            usage = _page_usage(agreement)
            over_capacity = usage is not None and any(
                clause is not None
                and clause.quantity is not None
                and usage + (item.quantity or 0) > clause.quantity
                for clause in [_page_deliverable(agreement)]
            )
            if over_capacity or re.search(r"\b(additional|extra)\b", item.raw_text):
                for clause in agreement.clauses:
                    if clause.type is ClauseType.RATE:
                        if clause.subtype == "hourly_rate" or (
                            clause.subtype == "effort_assumption" and _is_page_item(item)
                        ):
                            hits_by_id.setdefault(
                                clause.id,
                                _hit(clause, "context", _concept_match(item, clause), ("estimate",)),
                            )
                            item_matches[item.item_id].add(clause.id)

        if (
            ("logo" in item.concepts or "brand identity" in item.concepts)
            and not _preserves_existing(item.raw_text, "logo")
        ):
            for clause in agreement.clauses:
                if clause.type is ClauseType.RATE and clause.subtype in {"hourly_rate", "effort_assumption"}:
                    hits_by_id.setdefault(clause.id, _hit(clause, "context", (), ("estimate",)))
                    item_matches[item.item_id].add(clause.id)

    ordered_hits = [
        _hit(clause, hits_by_id[clause.id].relation, hits_by_id[clause.id].matched_concepts, hits_by_id[clause.id].matched_constraints)
        if clause.id in hits_by_id
        else None
        for clause in agreement.clauses
    ]
    hits = [hit for hit in ordered_hits if hit is not None]
    conflict_ids: list[str] = []
    for item in parsed.items:
        related = [clause for clause in agreement.clauses if clause.id in item_matches[item.item_id]]
        for included in related:
            if included.type not in {ClauseType.DELIVERABLE, ClauseType.LIMIT}:
                continue
            for excluded in related:
                if excluded.type is ClauseType.EXCLUSION and included.subtype == excluded.subtype:
                    for clause_id in (included.id, excluded.id):
                        if clause_id not in conflict_ids:
                            conflict_ids.append(clause_id)
    notes = []
    if not hits:
        notes.append("No typed agreement clause matched the request.")
    if parsed.missing_information:
        notes.append("The request contains unresolved or ambiguous terms.")
    return RetrieveOutput(
        hits=hits,
        conflict_clause_ids=conflict_ids,
        retrieval_notes=notes,
    )


def _clause_for(hit_id: str, agreement: Agreement) -> Clause | None:
    return next((clause for clause in agreement.clauses if clause.id == hit_id), None)


def _round_number(item: ParseItem) -> float | None:
    ordinal = r"\d+(?:st|nd|rd|th)|one|two|three|four|five|six|seven|eight|nine|ten|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"
    match = re.search(rf"\b(?:round|revision round)\s+({ordinal})\b", item.raw_text)
    if not match:
        match = re.search(rf"\b({ordinal})\s+revision(?:\s+round)?\b", item.raw_text)
    if not match:
        match = re.search(rf"\b({ordinal})\s+round\b", item.raw_text)
    if not match:
        return None
    token = match.group(1)
    digit_ordinal = re.fullmatch(r"(\d+)(?:st|nd|rd|th)", token)
    return float(digit_ordinal.group(1)) if digit_ordinal else _number(token)


def _display_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _display_currency(value: float) -> str:
    return f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"


def _estimate(
    parsed: ParseOutput,
    agreement: Agreement,
) -> tuple[float | None, float | None, str | None, list[str]]:
    rate = next(
        (clause.quantity for clause in agreement.clauses if clause.subtype == "hourly_rate" and clause.quantity is not None),
        agreement.pricing_rules.get("hourly_rate"),
    )
    effort_by_key = agreement.pricing_rules.get("effort_hours", {})
    efforts: list[tuple[float, float, float]] = []
    estimate_notes: list[str] = []
    needs_estimate = False
    for item in parsed.items:
        if not (
            _is_page_item(item)
            and _explicit_page_request(item)
            and re.search(r"\b(add|create|build|design)\b", item.raw_text)
        ):
            if "logo" in item.concepts and not _preserves_existing(item.raw_text, "logo"):
                needs_estimate = True
                estimate_notes.append(
                    "Logo is not included in the estimate because no explicit logo effort assumption is configured."
                )
            continue
        needs_estimate = True
        if item.quantity is None:
            estimate_notes.append(
                "The page item is not included in the estimate because its quantity is unspecified."
            )
            continue
        key = "additional_marketing_page"
        effort = effort_by_key.get(key) if isinstance(effort_by_key, dict) else None
        if effort is None:
            effort_clause = next(
                (clause for clause in agreement.clauses if clause.subtype == "effort_assumption" and _is_page_item(item)),
                None,
            )
            effort = effort_clause.quantity if effort_clause else None
        if effort is None:
            estimate_notes.append(
                "The page item is not included in the estimate because no explicit page effort assumption is configured."
            )
        else:
            quantity = float(item.quantity)
            effort_per_item = float(effort)
            efforts.append((quantity, effort_per_item, quantity * effort_per_item))
    if not needs_estimate:
        return None, None, None, []
    if not efforts or rate is None:
        return (
            None,
            None,
            "Estimate unavailable: an explicit effort assumption and hourly rate are required.",
            estimate_notes,
        )
    hours = sum(total for _, _, total in efforts)
    cost = hours * float(rate)
    formula = "; ".join(
        f"{_display_number(quantity)} pages × {_display_number(effort)} hours/page = {_display_number(total)} estimated hours"
        for quantity, effort, total in efforts
    )
    label = (
        f"Estimate: {formula}; {_display_number(hours)} hours × "
        f"${_display_currency(float(rate))}/hour = ${_display_currency(cost)}."
    )
    if estimate_notes:
        label = f"{label} {' '.join(estimate_notes)}"
    return hours, cost, label, estimate_notes


def classify_request(parsed: ParseOutput, retrieved: RetrieveOutput, agreement: Agreement) -> ClassifyOutput:
    """Apply deterministic precedence rules after evidence retrieval."""

    tags: list[str] = []
    rationale: list[str] = []
    rules: list[str] = []
    scheduling_flag: str | None = None
    classification = Classification.IN_SCOPE
    evidence_ids = [
        hit.clause_id
        for hit in retrieved.hits
        if "preservation" not in hit.matched_constraints
    ]

    deadline = next((clause for clause in agreement.clauses if clause.type is ClauseType.DEADLINE), None)
    has_schedule = any("launch" in item.concepts or item.intent == "schedule" for item in parsed.items)
    if has_schedule:
        requested_date = _date_in(parsed.normalized_text)
        agreed_date = deadline.qualifiers[0] if deadline and deadline.qualifiers else None
        if deadline and requested_date and agreed_date and requested_date != agreed_date:
            classification = Classification.NEEDS_CLARIFICATION
            scheduling_flag = "deadline_conflict"
            tags.append("scheduling_conflict")
            rationale.append("The requested date conflicts with the agreed deadline; confirm the schedule.")
            rules.append("deadline_conflict_precedes_scope_classification")
        elif has_schedule and deadline and requested_date == agreed_date:
            rationale.append("The requested launch date matches the agreed deadline.")

    for item in parsed.items:
        item_hits = [
            hit
            for hit in retrieved.hits
            if (clause := _clause_for(hit.clause_id, agreement)) is not None
            and (
                _concept_match(item, clause)
                or (hit.relation == "context" and hit.clause_type is ClauseType.RATE)
            )
        ]
        if not item_hits and not item.ambiguity_tags:
            classification = Classification.NEEDS_CLARIFICATION
            if "no_matching_clause" not in tags:
                tags.append("no_matching_clause")
            rationale.append("No matching contractual evidence was found.")
            rules.append("no_evidence_is_not_a_definitive_exclusion")
            continue
        exclusion_is_actionable = any(
            hit.clause_type is ClauseType.EXCLUSION for hit in item_hits
        ) and not (
            _copy_request_is_ambiguous(item.raw_text, item.concepts)
            or _preserves_existing(item.raw_text, "copy")
            or _preserves_existing(item.raw_text, "logo")
        )
        if exclusion_is_actionable:
            generic_seo = "seo" in item.concepts and not _has_explicit_metadata(item)
            if not generic_seo:
                specific_include = any(
                    hit.clause_type is ClauseType.DELIVERABLE and (
                        "seo metadata" in hit.matched_concepts or _has_explicit_metadata(item)
                    )
                    for hit in item_hits
                )
                if not specific_include:
                    classification = Classification.POTENTIALLY_OUT_OF_SCOPE
                    if "excluded_work" not in tags and "logo" not in item.concepts:
                        tags.append("excluded_work")
                    rationale.append("The request matches work explicitly excluded by the agreement.")
                    rules.append("explicit_exclusion_is_actionable_evidence")
        if item.ambiguity_tags:
            classification = Classification.NEEDS_CLARIFICATION
            for tag in item.ambiguity_tags:
                if tag not in tags:
                    tags.append(tag)
            rationale.append("Clarify the request's unresolved intent, quantity, or meaning.")
            rules.append("ambiguity_requires_clarification")

        if _is_page_item(item) and _explicit_page_request(item) and re.search(r"\b(add|create|build)\b", item.raw_text):
            deliverable = _page_deliverable(agreement)
            usage = _page_usage(agreement)
            if usage is None:
                classification = Classification.NEEDS_CLARIFICATION
                if "current_usage_unknown" not in tags:
                    tags.append("current_usage_unknown")
                rationale.append("Current page usage is not recorded, so remaining capacity is unknown.")
                rules.append("capacity_requires_current_usage")
            elif deliverable and deliverable.quantity is not None and item.quantity is not None and usage + item.quantity > deliverable.quantity:
                classification = Classification.POTENTIALLY_OUT_OF_SCOPE
                rationale.append("The requested pages exceed the remaining included deliverable allowance.")
                rules.append("deliverable_quantity_is_checked_against_current_usage")
            elif item.quantity is None:
                classification = Classification.NEEDS_CLARIFICATION
            if re.search(r"\b(additional|extra)\b", item.raw_text) and (usage is None or deliverable is None):
                classification = Classification.NEEDS_CLARIFICATION

            if re.search(r"\b(additional|extra)\b", item.raw_text) or (
                usage is not None
                and deliverable is not None
                and deliverable.quantity is not None
                and item.quantity is not None
                and usage + item.quantity > deliverable.quantity
            ):
                effort_exists = any(
                    clause.subtype == "effort_assumption"
                    and ("marketing page" in clause.source_text.lower() or "page" in clause.source_text.lower())
                    for clause in agreement.clauses
                )
                rate_exists = any(
                    clause.subtype == "hourly_rate" and clause.quantity is not None
                    for clause in agreement.clauses
                ) or agreement.pricing_rules.get("hourly_rate") is not None
                if not effort_exists or not rate_exists:
                    if "estimate_effort_assumption_missing" not in tags:
                        tags.append("estimate_effort_assumption_missing")
                    rationale.append("A complete estimate requires both an explicit effort assumption and an hourly rate.")

        if "revision" in item.concepts:
            limit = next((clause for clause in agreement.clauses if clause.subtype == "revision_round"), None)
            requested_round = _round_number(item)
            if limit and requested_round is not None and limit.quantity is not None and requested_round > limit.quantity:
                classification = Classification.POTENTIALLY_OUT_OF_SCOPE
                if "revision_allowance_exceeded" not in tags:
                    tags.append("revision_allowance_exceeded")
                rationale.append("The requested revision round exceeds the included allowance.")
                rules.append("revision_round_allowance_is_inclusive")

        if "logo" in item.concepts and not _preserves_existing(item.raw_text, "logo"):
            effort_exists = any(clause.subtype == "effort_assumption" and "logo" in clause.source_text.lower() for clause in agreement.clauses)
            if not effort_exists:
                tags.append("logo_effort_assumption_missing")
                rationale.append("Logo work is excluded and has no explicit effort assumption for an estimate.")

    if retrieved.conflict_clause_ids:
        classification = Classification.NEEDS_CLARIFICATION
        tags = [tag for tag in tags if tag != "excluded_work"]
        rationale.append("Relevant agreement clauses contradict one another.")
        rules.append("contradictory_evidence_requires_clarification")

    # A schedule conflict always wins, including when another item is excluded.
    if not parsed.items:
        classification = Classification.NEEDS_CLARIFICATION
        if "no_matching_clause" not in tags:
            tags.append("no_matching_clause")
        rationale.append("No actionable request item was provided.")
        rules.append("empty_request_requires_clarification")

    if scheduling_flag == "deadline_conflict":
        classification = Classification.NEEDS_CLARIFICATION

    scope_evidence_ids = [
        hit.clause_id
        for hit in retrieved.hits
        if hit.clause_type in {ClauseType.DELIVERABLE, ClauseType.EXCLUSION, ClauseType.LIMIT}
    ]
    pricing_evidence_ids = [
        hit.clause_id for hit in retrieved.hits if hit.clause_type is ClauseType.RATE
    ]
    passed_checks: list[str] = []
    for item in parsed.items:
        if "revision" in item.concepts:
            limit = next(
                (clause for clause in agreement.clauses if clause.subtype == "revision_round"),
                None,
            )
            requested_round = _round_number(item)
            if (
                limit
                and requested_round is not None
                and limit.quantity is not None
                and requested_round <= limit.quantity
            ):
                passed_checks.append(
                    f"revision round {int(requested_round)} is within the allowance in {limit.id}"
                )
        if _is_page_item(item) and _explicit_page_request(item):
            deliverable = _page_deliverable(agreement)
            usage = _page_usage(agreement)
            if (
                deliverable
                and deliverable.quantity is not None
                and usage is not None
                and item.quantity is not None
                and usage + item.quantity <= deliverable.quantity
            ):
                passed_checks.append(
                    f"the requested quantity fits within the allowance in {deliverable.id}"
                )
        if "seo metadata" in item.concepts and "d-seo-metadata" in evidence_ids:
            passed_checks.append("the requested metadata matches the included SEO metadata clause d-seo-metadata")
    if has_schedule and scheduling_flag is None and deadline and _date_in(parsed.normalized_text) == (
        deadline.qualifiers[0] if deadline.qualifiers else None
    ):
        passed_checks.append(f"the requested date matches the deadline in {deadline.id}")
    for item in parsed.items:
        if "logo" in item.concepts and _preserves_existing(item.raw_text, "logo"):
            logo_clause = next(
                (hit.clause_id for hit in retrieved.hits if hit.clause_id == "x-logo-design"),
                "x-logo-design",
            )
            passed_checks.append(
                f"the logo is kept as-is, so {logo_clause} is context and does not trigger the exclusion"
            )

    prior_rationale = next(iter(dict.fromkeys(rationale)), None)
    if classification is Classification.IN_SCOPE:
        checks = "; ".join(passed_checks) or "no exclusion, quantity, revision, or scheduling conflict was found"
        rationale = [
            f"Scope evidence clauses {', '.join(scope_evidence_ids) or 'none'} support this request, and {checks}.",
        ]
        if pricing_evidence_ids:
            rationale.append(
                f"Pricing context clauses {', '.join(pricing_evidence_ids)} are separate calculation inputs and do not determine scope."
            )
        rules.extend(
            (
                "supporting_evidence_is_required",
                "all_applicable_limits_and_exclusions_passed",
            )
        )
    elif classification is Classification.POTENTIALLY_OUT_OF_SCOPE:
        out_reasons: list[str] = []
        for item in parsed.items:
            related_exclusions: list[EvidenceHit] = []
            for hit in retrieved.hits:
                clause = _clause_for(hit.clause_id, agreement)
                if (
                    hit.clause_type is ClauseType.EXCLUSION
                    and clause is not None
                    and _concept_match(item, clause)
                ):
                    related_exclusions.append(hit)
            for hit in related_exclusions:
                subject = "logo request" if "logo" in item.concepts else "request"
                out_reasons.append(f"the {subject} matches exclusion {hit.clause_id}")
        if "deliverable_quantity_is_checked_against_current_usage" in rules:
            for item in parsed.items:
                if not (_is_page_item(item) and item.quantity is not None):
                    continue
                deliverable = _page_deliverable(agreement)
                usage = _page_usage(agreement)
                if deliverable and deliverable.quantity is not None and usage is not None:
                    out_reasons.append(
                        f"the page allowance in {deliverable.id} is used up ({_display_number(float(usage))} of {_display_number(float(deliverable.quantity))} delivered, so {_display_number(float(item.quantity))} more would exceed it)"
                    )
                    break
        if "revision_round_allowance_is_inclusive" in rules:
            out_reasons.append("the requested revision round exceeds the included allowance")
        detail = " and ".join(dict.fromkeys(out_reasons)) or (prior_rationale or "an exclusion or allowance check requires scope review")
        detail = detail.rstrip(".!? ")
        rationale = [
            f"Scope evidence clauses {', '.join(scope_evidence_ids) or 'none'} indicate that {detail[0].lower() + detail[1:]}.",
        ]
        if pricing_evidence_ids:
            if estimate_notes := _estimate(parsed, agreement)[3]:
                rationale.append(
                    f"Pricing context clauses {', '.join(pricing_evidence_ids)} support an estimate for the page work only; {' '.join(estimate_notes)}"
                )
            else:
                rationale.append(
                    f"Pricing context clauses {', '.join(pricing_evidence_ids)} are separate calculation inputs and do not determine scope."
                )
        rules.append("explicit_exclusion_or_exceeded_limit_requires_scope_review")
    else:
        if scheduling_flag == "deadline_conflict":
            reason = "the requested date conflicts with the agreed deadline"
        elif "no_matching_clause" in tags:
            reason = "no matching contractual evidence was found"
        elif "contradictory_evidence_requires_clarification" in rules:
            reason = "relevant agreement clauses contradict one another"
        elif tags:
            reason = "the request contains unresolved or ambiguous details"
        else:
            reason = "the available evidence does not resolve the request"
        rationale = [
            f"Scope evidence clauses {', '.join(scope_evidence_ids) or 'none'} were retrieved, but clarification is required because {reason}.",
        ]
        preserved_context_ids = [
            hit.clause_id
            for hit in retrieved.hits
            if "preservation" in hit.matched_constraints
        ]
        if preserved_context_ids:
            rationale.append(
                f"Preservation context {', '.join(preserved_context_ids)} does not trigger the exclusion."
            )
        rules.append("uncertainty_or_conflict_requires_human_clarification")

    return ClassifyOutput(
        classification=classification,
        rationale=rationale,
        evidence_clause_ids=evidence_ids,
        uncertainty_tags=list(dict.fromkeys(tags)),
        conflicting_clause_ids=list(retrieved.conflict_clause_ids),
        scheduling_flag=scheduling_flag,
        decision_rules=list(dict.fromkeys(rules)),
    )


def _clarification_questions(
    parsed: ParseOutput,
    classified: ClassifyOutput,
    retrieved: RetrieveOutput,
    agreement: Agreement,
) -> list[str]:
    """Turn deterministic uncertainty signals into concrete client questions."""

    questions: list[str] = []
    for item in parsed.items:
        if "seo_meaning_ambiguous" in item.ambiguity_tags:
            metadata_clause = next(
                (
                    clause
                    for clause in agreement.clauses
                    if clause.id == "d-seo-metadata"
                    and clause.type is ClauseType.DELIVERABLE
                ),
                None,
            )
            strategy_clause = next(
                (
                    clause
                    for clause in agreement.clauses
                    if clause.id == "x-seo-strategy"
                    and clause.type is ClauseType.EXCLUSION
                ),
                None,
            )
            if metadata_clause and strategy_clause:
                quantity = _display_number(float(metadata_clause.quantity)) if metadata_clause.quantity else "the included"
                questions.append(
                    f"When you say improve SEO, do you mean SEO metadata (included for up to {quantity} pages under {metadata_clause.id}) or SEO strategy/keyword research (excluded under {strategy_clause.id})?"
                )
            else:
                questions.append(
                    "When you say improve SEO, do you mean metadata, strategy, keyword research, or another specific SEO task?"
                )
        if "design_intent_unspecified" in item.ambiguity_tags:
            questions.append(
                "Which pages should be changed, and what specific changes should we make?"
            )
        if "quantity_missing" in item.ambiguity_tags:
            questions.append("How many pages or items should we add or change?")
        if "current_usage_unknown" in classified.uncertainty_tags:
            questions.append("How many marketing pages have already been delivered so we can check the remaining allowance?")

    if classified.scheduling_flag == "deadline_conflict":
        questions.append("Should we keep the agreed launch deadline, or would you like to request a schedule change for review?")
    if "no_matching_clause" in classified.uncertainty_tags:
        questions.append(
            "This request does not match any listed deliverable or exclusion. Please confirm whether it is new work that should be reviewed as a potential scope change."
        )
    if classified.conflicting_clause_ids:
        questions.append(
            f"Which agreement language should govern: {', '.join(classified.conflicting_clause_ids)}?"
        )
    if not questions:
        questions.append("What specific outcome, quantity, and acceptance criteria should we review against the agreement?")
    return list(dict.fromkeys(questions))


def _draft(
    parsed: ParseOutput,
    classified: ClassifyOutput,
    agreement: Agreement,
    retrieved: RetrieveOutput,
) -> DraftAction:
    hours, cost, estimate_label, estimate_notes = _estimate(parsed, agreement)
    clarification_questions = (
        _clarification_questions(parsed, classified, retrieved, agreement)
        if classified.classification is Classification.NEEDS_CLARIFICATION
        else []
    )
    if classified.classification is Classification.IN_SCOPE:
        kind, title = "response", "Confirm requested work"
        body = "The request is supported by the cited agreement clauses and can proceed to human review."
    elif classified.classification is Classification.POTENTIALLY_OUT_OF_SCOPE:
        kind, title = "change_order", "Prepare a scope change review"
        body = "The request may exceed the agreement or match excluded work; confirm a change order before proceeding."
    else:
        kind, title = "clarification", "Request clarification"
        body = "Please clarify the following before deciding scope:\n\n" + "\n".join(
            f"- {question}" for question in clarification_questions
        )
    return DraftAction(
        kind=kind,
        title=title,
        body=body,
        assumptions=list(classified.uncertainty_tags),
        estimated_hours=hours,
        estimated_cost=cost,
        estimate_label=estimate_label,
        estimate_notes=estimate_notes,
        clarification_questions=clarification_questions,
    )


def analyze_request(request: Request | str, agreement: Agreement | Project, request_id: str = "request-1") -> AnalysisResult:
    """Run parse, typed retrieval, classification, and draft stages."""

    if isinstance(request, Project) and isinstance(agreement, Request):
        return analyze_request(agreement, request.agreement, request_id=agreement.id)
    if isinstance(agreement, Project):
        project = agreement
        agreement = project.agreement
        if isinstance(request, str):
            request = Request(id=request_id, project_id=project.id, text=request)
    elif isinstance(request, str):
        request = Request(id=request_id, project_id="project-1", text=request)
    if not isinstance(request, Request):
        raise TypeError("request must be a Request or string")
    parsed = parse_request(request.text)
    retrieved = retrieve_evidence(parsed, agreement)
    classified = classify_request(parsed, retrieved, agreement)
    draft = _draft(parsed, classified, agreement, retrieved)
    trace = PipelineTrace(parse=parsed, retrieve=retrieved, classify=classified, draft=draft)
    return AnalysisResult(
        request_id=request.id,
        classification=classified.classification,
        evidence_clause_ids=list(classified.evidence_clause_ids),
        uncertainty_reasons=list(classified.uncertainty_tags),
        conflicting_clause_ids=list(classified.conflicting_clause_ids),
        scheduling_flag=classified.scheduling_flag,
        trace=trace,
        draft=draft,
    )


def analyze(project: Project, request: Request | str) -> AnalysisResult:
    return analyze_request(request, project)
