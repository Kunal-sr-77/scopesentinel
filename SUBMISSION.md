# ScopeSentinel: Evidence-backed, deterministic scope review for small agencies

## Description

### Problem

I built ScopeSentinel for small agencies where client requests grow beyond the
agreement. Clients ask for extra pages, extra revision rounds, or excluded
work, and small agencies can end up doing it unpaid. I need a fast answer
grounded in the agreement rather than a vague yes or no.

### What I built

ScopeSentinel lets me set up a project agreement, submit a natural-language
request, inspect the result, and approve a local review. Its pipeline
has four stages: **parse**, **retrieve**, **classify**, and **draft**. The trace
shows the parsed request, retrieved evidence, and draft response or change-order
summary.

The classifier returns exactly three verdicts: `IN_SCOPE`,
`POTENTIALLY_OUT_OF_SCOPE`, or `NEEDS_CLARIFICATION`. Retrieved evidence keeps
the exact agreement clause text, so the result can show why a decision was
made. Estimates are produced only when both a configured effort assumption and
hourly rate are available. For example, the tested case calculates **2 pages
x 4 hours x $125 = $1,000**; logo work with no configured effort assumption is
not included in that estimate.

The final step is a human approval checkpoint. Approval records a local review;
it never sends messages, approves charges, or edits a contract.

### Design choices

I kept the decision path deterministic and offline. There are no LLM calls,
network calls, or external services in the analysis path. When evidence is
missing, contradictory, ambiguous, or unfamiliar, the system falls back to
`NEEDS_CLARIFICATION` instead of pretending to know the answer.

### How I used OmniRush

I used OmniRush to shape the interfaces, implement the workflow, run QA, and
document the reproducible build with three parallel sub-agent roles:

- The **contract-analysis sub-agent** built the agreement parser, request
  parser, typed evidence retrieval, deterministic classification, and estimate
  rules.
- The **frontend sub-agent** built the Flask/Jinja setup, analysis, dashboard,
  history, trace, and human-approval screens.
- The **QA sub-agent** added regression and boundary coverage, the fixed
  evaluation report, the 15-case independent holdout, and the fresh 10-case
  holdout report.

The testing and manual-review loop found several concrete bugs that are now
covered by regression tests: ordinal requests such as a **3rd revision round**
were not consistently checked against the two-round limit (`bf28a6d`); mixed
page-and-logo requests lost the supported partial page estimate
(`2365a12`); setup-form clause metadata differed from the sample agreement and
could skip the revision-limit check (`ba7287c`); and preservation language such
as “keep the logo as-is” could incorrectly trigger an exclusion or leak into
an unrelated request item (`9fc9108`).

### Reproducibility

The repository is available at:
https://github.com/Kunal-sr-77/scopesentinel

I pin Python 3.12.10 and dependencies and provide Docker and one offline test
command. The exact container checks are:

```bash
docker build -t scopesentinel .
docker run --rm --network none scopesentinel make test
```

`make test` currently runs **44 tests** and passes without network access.

### Honest limits

The evaluation sets were used while tuning the rules, so their scores do not
measure accuracy on unseen requests; unseen-request accuracy has not been
measured. The engine is rule-based, English-only, and uses a curated vocabulary
rather than general semantic understanding. Unfamiliar phrasings can fall back
to `NEEDS_CLARIFICATION`. ScopeSentinel makes no legal determination. Future
work is a hybrid design in which an LLM extracts structured fields while
deterministic rules make the final scope decision.
