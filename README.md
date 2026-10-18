# ScopeSentinel

ScopeSentinel is an evidence-backed scope-creep review tool for small web
development agencies and software studios. It compares an incoming client
request with typed agreement clauses, shows the supporting source text, and
prepares a human-reviewable next action.

## MVP cut line

The implemented MVP includes:

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

The MVP is implemented and includes project setup and sample loading, request
intake, deterministic local clause retrieval and classification, exact source
evidence, a serializable `PipelineTrace`, draft response or change order,
explicit human approval, and JSON-backed request history. `make test` runs the
regression and application suite; `make eval` reports the fixed evaluation and
independent holdout suites without affecting the build gate.

## Architecture

- Python 3.12.10
- Flask with Jinja templates
- Vanilla CSS and JavaScript for the browser UI
- JSON file persistence using atomic replacement
- Python `unittest` with no network access or external API
- No database and no native dependencies

The shared interfaces are in `scopesentinel/domain.py`. The main pipeline
returns a serializable `PipelineTrace` with `parse`, `retrieve`, `classify`,
and `draft` outputs. Agreement clauses preserve their original `source_text`
and are typed as deliverables, exclusions, limits, rates, or deadlines.

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

## Docker

Build the image:

```bash
docker build -t scopesentinel .
```

Run the tests without network access:

```bash
docker run --rm --network none scopesentinel make test
```

Run the application with persistent history:

```bash
docker run --rm -p 8000:8000 -v scopesentinel-data:/app/data scopesentinel
```

Without `-v`, history is lost when the container stops. Reset the persistent
history volume with:

```bash
docker volume rm scopesentinel-data
```

## Test and evaluation

After activating the project-local virtual environment and installing the
locked dependencies, run the canonical local test command:

```bash
. .venv/bin/activate
python -m pip install --requirement requirements.lock
make test
```

Tests use temporary JSON files. They never write to `data/history.json`.

`make test` currently runs **44 tests**: regression, boundary, setup-path, and
application tests. It excludes strict holdout assertions. Run the separate
evaluation report with:

```bash
make eval
```

`make eval` always prints accuracy and every failure without failing the build.

## Evaluation results

The fixed Step 2 evaluation set is in `scopesentinel/evaluation.py` and contains
16 labelled scenarios, including worked examples A-E, false-positive keyword
matches, missing quantities, unknown current usage, and scheduling conflicts.
Each case specifies its expected classification, supporting evidence clause
IDs, uncertainty tags, and scheduling flag where applicable. The fixed set
reports **16/16**.

These sets were used while tuning the rules, so these scores are not evidence
of accuracy on unseen requests. Accuracy on genuinely unseen requests has not
been measured.

### Independent holdout

The independent QA set is in `tests/holdout_cases.py`. It contains **15 new
natural-language scenarios**, including **4 false-positive traps**, and is
evaluated separately from the original 16 cases. Strict accuracy across
classification, evidence clause IDs, uncertainty tags, scheduling flags, and
the requested estimate fields is **15/15**.

The original holdout findings led to general rules for:

- ordinal revision rounds such as “fourth round”;
- preservation and negation language such as “keep”, “unchanged”, and
  “existing wording”;
- explicit page metadata language;
- quantity words and vague quantifiers such as “two”, “a few”, and “several”;
- page-specific evidence selection for SEO metadata versus generic pages.

The holdout report command is:

```bash
make eval
```

The strict report currently passes with no failures. The boundary suite covers
direct approval bypass, empty input, malformed input, and corrupted history
using temporary JSON files. Corrupted history is quarantined as
`history.corrupt-<timestamp>.json`, the store starts empty, and the dashboard
shows a visible recovery notice.

### Fresh holdout

The QA agent added a separate set of exactly **10 fresh scenarios**, H16–H25,
in `tests/fresh_holdout_cases.py`, with **4 false-positive traps** and different
client phrasing from the first holdout. Its strict accuracy is separately
reported as **10/10**, with no failures. `make eval` prints both holdout
results without failing the build.

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
   Please add two case-study pages and design a new logo.
   ```

   The page shows `POTENTIALLY_OUT_OF_SCOPE`, the page-capacity and logo
   exclusion evidence, and the partial estimate:
   `2 pages × 4 hours/page = 8 estimated hours; 8 hours × $125/hour = $1,000`.
   The logo is explicitly excluded from that estimate because it has no effort
   assumption.
5. Submit:

   ```text
   Can you make the site feel more premium and improve SEO?
   ```

   The clarification draft asks which pages and changes the client wants, and
   whether SEO means included metadata or excluded strategy/keyword research.
6. Submit:

   ```text
   Can you do a 3rd round of changes on the pricing page.
   ```

   The page shows `POTENTIALLY_OUT_OF_SCOPE` because the sample agreement
   allows two revision rounds.
7. Review the evidence and draft, check the acknowledgment box, and approve.
   Approval only records a local review; it never sends a message, approves a
   charge, or modifies a contract. Visit **History** to see the saved record.

## Built with OmniRush

The project was built with OmniRush using a deterministic core plus parallel
contract-analysis, frontend, and QA sub-agents. Each request exposes four
pipeline stages: **parse**, **retrieve**, **classify**, and **draft**.

## Known issue fixed

Manual testing found that projects saved through the setup form could produce
different clause metadata from the built-in sample, which skipped the
revision-limit check. This was fixed in commit `ba7287c`; regression tests now
compare the setup-form and sample paths, including the fixed evaluation and
both holdout suites.

## Limitations

- The engine uses a curated synonym map rather than general semantic
  understanding.
- Reliable quantity and limit checks require explicit units and quantities;
  vague or unsupported quantities fall toward clarification.
- The parser is English-only.
- The setup editor supports a single sample-project agreement format with
  line-oriented clauses, not complex nested conditions or amendments.
- ScopeSentinel makes no legal determination.
- Estimates are produced only from configured effort assumptions and rates.
- Revision rounds are read from the request text only; the app does not track
  revision rounds already used per page.
- The rule-based engine can miss phrasings it has not seen. When it cannot
  resolve a request safely, it fails toward `NEEDS_CLARIFICATION`.
- JSON history is local and intentionally small. Corrupted JSON is quarantined
  and replaced with empty history, but there is no multi-user locking layer.

**Future work:** use a hybrid design where an LLM extracts structured fields
and deterministic rules make the final scope call.

## Safety boundaries

ScopeSentinel provides a commercial scope assessment, not a legal conclusion.
Unclear or contradictory agreement evidence produces
`NEEDS_CLARIFICATION`. Scheduling conflicts produce a visible scheduling flag
and `NEEDS_CLARIFICATION` by default; they do not independently produce
`POTENTIALLY_OUT_OF_SCOPE` unless a later explicit contract rule establishes
that consequence.
