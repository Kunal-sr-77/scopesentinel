# ScopeSentinel

ScopeSentinel is an evidence-backed scope-creep review tool for small web
development agencies and software studios. It compares an incoming client
request with typed agreement clauses, shows the supporting source text, and
prepares a human-reviewable next action.

## MVP cut line

The submission target is the evening of **19 October 2026**, ahead of the
buildathon deadline of **20 October 2026 at 11:59 PM IST**.

The committed MVP will include:

- project setup and sample project loading,
- request intake,
- deterministic local clause retrieval and classification,
- exact source evidence and visible pipeline trace,
- draft response or change order,
- explicit human approval,
- JSON-backed request history.

There is no external LLM, network call, automatic message sending, automatic
charge approval, or contract modification.

## Current status

Steps 1–3 are implemented and Step 4 QA is recorded. The original evaluation
set is perfect, but the independent holdout set intentionally remains failing
until its findings are reviewed; no engine tuning has been made against those
holdout failures.

## Architecture

- Python 3.12.10
- Flask with Jinja templates
- Vanilla CSS and JavaScript for the browser UI
- JSON file persistence using atomic replacement
- Python `unittest` with no network access or external API
- No database and no native dependencies

The shared interfaces are in `scopesentinel/domain.py`. The main pipeline will
return a serializable `PipelineTrace` with `parse`, `retrieve`, `classify`, and
`draft` outputs. Agreement clauses preserve their original `source_text` and
are typed as deliverables, exclusions, limits, rates, or deadlines.

### Dependency pin audit

The following exact pins were checked against the PyPI JSON API on 17 October
2026. All release uploads are on or before the 3 October 2026 cutoff.

| Package | Version | PyPI release date |
| --- | --- | --- |
| blinker | 1.9.0 | 2024-11-08 |
| click | 8.2.1 | 2025-05-20 |
| Flask | 3.1.2 | 2025-08-19 |
| itsdangerous | 2.2.0 | 2024-04-16 |
| Jinja2 | 3.1.6 | 2025-03-05 |
| MarkupSafe | 3.0.2 | 2024-10-18 |
| Werkzeug | 3.1.3 | 2024-11-08 |

## Local setup

Python 3.12.10 is required. A virtual environment is recommended:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --requirement requirements.lock
```

No credentials or external services are required. Optional local settings are
listed in `.env.example`.

## Run locally

```bash
python app.py
```

Open <http://localhost:8000>.

## Exact Docker verification commands

These are the two canonical commands for the buildathon:

```bash
docker build -t scopesentinel:step1 .
docker run --rm --network none scopesentinel:step1 make test
```

The second command runs the exact `make test` target with networking disabled.
The application itself can be started with:

```bash
docker run --rm -p 8000:8000 scopesentinel:step1
```

## Test

After activating the project-local virtual environment and installing the
locked dependencies, run the canonical local test command:

```bash
. .venv/bin/activate
python -m pip install --requirement requirements.lock
make test
```

Tests use temporary JSON files. They never write to `data/history.json`.

## Evaluation set

The fixed Step 2 evaluation set is in `scopesentinel/evaluation.py` and contains
16 labelled scenarios, including worked examples A-E, false-positive keyword
matches, missing quantities, unknown current usage, and scheduling conflicts.
Each case specifies its expected classification, supporting evidence clause
IDs, uncertainty tags, and scheduling flag where applicable. The measured
evaluation accuracy is **16/16 (100%)** in the latest integrated run. This is
strict accuracy across classification, evidence clause IDs, uncertainty tags,
and scheduling flags; it is not a legal or contractual accuracy claim.

### Independent Step 4 holdout

The independent QA set is in `tests/holdout_cases.py`. It contains **15 new
natural-language scenarios**, including **4 false-positive traps**, and is
evaluated separately from the original 16 cases. Strict accuracy across
classification, evidence clause IDs, uncertainty tags, scheduling flags, and
the requested estimate fields is currently **8/15 (53.33%)**.

The seven reported holdout failures are preserved in the QA report rather than
being tuned away:

- **H03** — “fourth round of edits” is treated as in scope instead of exceeding
  the revision allowance.
- **H06** — “copy existing wording without writing new copy” is treated as an
  exclusion instead of clarification.
- **H07** — explicit page title and description tags remain ambiguous SEO
  instead of resolving to included metadata.
- **H08** — “a few more landing pages” does not produce a missing-quantity
  signal.
- **H13** — “two new pages and send an estimate” produces a one-page estimate
  because “an estimate” is misread as quantity one.
- **H14** — an unchanged-logo mention triggers the logo exclusion for an
  otherwise in-scope page request.
- **H15** — “keep all copy exactly as supplied” adds an exclusion and quantity
  signal to an otherwise design-ambiguity case.

The holdout command is:

```bash
. .venv/bin/activate
python -m unittest discover -s tests -p 'test_holdout.py' -v
```

It currently fails on the strict holdout assertion by design, with the seven
findings above. The Step 4 boundary suite passes and covers direct approval
bypass, empty input, malformed input, and corrupted history using temporary
JSON files. Corrupted history currently raises `json.JSONDecodeError` at the
store boundary; it is recorded as a limitation rather than silently repaired.

## Demo walkthrough

1. Start the app with `python app.py` and open <http://localhost:8000>.
2. Open **Project setup** to review or edit the sample Northstar agreement.
   Current page usage is editable; the sample starts with five marketing pages
   delivered, a two-round revision allowance, and the configured rate and page
   effort assumption.
3. Choose **New request** and paste:

   ```text
   Please revise the existing homepage hero during revision round two.
   ```

   The detail page shows `IN_SCOPE`, the exact deliverable and revision clauses,
   the four-stage trace, and a confirmation draft.
4. Submit:

   ```text
   Please improve SEO.
   ```

   The clarification draft asks whether the client means included metadata or
   excluded strategy/keyword research.
5. Submit:

   ```text
   Please add two case-study pages and design a new logo.
   ```

   The page shows `POTENTIALLY_OUT_OF_SCOPE`, the page-capacity and logo
   exclusion evidence, and the partial estimate:
   `2 pages × 4 hours/page = 8 estimated hours; 8 hours × $125/hour = $1,000`.
   The logo is explicitly excluded from that estimate because it has no effort
   assumption.
6. Review the evidence and draft, check the acknowledgment box, and approve.
   Approval only records a local review; it never sends a message, approves a
   charge, or modifies a contract. Visit **History** to see the saved record.

## Limitations

- The classifier is deterministic and transparent, not a general semantic or
  legal reasoning system. It uses a curated synonym vocabulary and typed
  agreement fields.
- Vague quantities, ordinal wording, copied-content intent, and compound
  requests can require clarification or produce the holdout findings listed
  above.
- Agreement setup is line-oriented. Complex nested conditions, precedence
  language, and amendments are not modeled in this MVP.
- JSON history is local and intentionally small. Corrupted JSON currently
  surfaces as `json.JSONDecodeError`; there is no recovery or multi-user
  locking layer.
- Estimates are not legal, financial, or contractual commitments. They appear
  only when explicit effort and rate assumptions support them, and all actions
  require human review.
- The current buildathon environment has not verified a clean Docker build in
  this sandbox when base-image layer extraction rejects `lchown`; the exact
  Docker commands remain documented for a Docker-capable Linux host.

## Safety boundaries

ScopeSentinel provides a commercial scope assessment, not a legal conclusion.
Unclear or contradictory agreement evidence produces
`NEEDS_CLARIFICATION`. Scheduling conflicts produce a visible scheduling flag
and `NEEDS_CLARIFICATION` by default; they do not independently produce
`POTENTIALLY_OUT_OF_SCOPE` unless a later explicit contract rule establishes
that consequence.
