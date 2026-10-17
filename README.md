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

The Step 1 skeleton is committed: the domain interfaces, JSON persistence
boundary, Flask application shell, pinned runtime, lockfile, Dockerfile, and
offline test command are established. Analysis and UI behavior are intentionally
not yet implemented in this skeleton. A clean Docker build and the
network-isolated container test are required gates before UI work begins.

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
evaluation accuracy will be reported after the analysis engine is integrated;
no accuracy claim is made before that check runs.

## Safety boundaries

ScopeSentinel provides a commercial scope assessment, not a legal conclusion.
Unclear or contradictory agreement evidence produces
`NEEDS_CLARIFICATION`. Scheduling conflicts produce a visible scheduling flag
and `NEEDS_CLARIFICATION` by default; they do not independently produce
`POTENTIALLY_OUT_OF_SCOPE` unless a later explicit contract rule establishes
that consequence.
