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

Step 1 is complete: the domain interfaces, JSON persistence boundary, Flask
application shell, pinned runtime, lockfile, Dockerfile, and offline test
command are established. Analysis and UI behavior are intentionally not yet
implemented in this skeleton.

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

The canonical local test command is:

```bash
make test
```

Tests use temporary JSON files. They never write to `data/history.json`.

## Evaluation set

Step 4 will add a fixed evaluation set of at least 15 scenarios. Each scenario
will specify its expected classification, supporting evidence clause IDs, and
expected uncertainty behavior, including false positives where a keyword
matches but the request is excluded or ambiguous. The README will report the
measured evaluation accuracy after the set is implemented; no accuracy claim
is made by this skeleton.

## Safety boundaries

ScopeSentinel provides a commercial scope assessment, not a legal conclusion.
Unclear or contradictory agreement evidence produces
`NEEDS_CLARIFICATION`. Scheduling conflicts produce a visible scheduling flag
and `NEEDS_CLARIFICATION` by default; they do not independently produce
`POTENTIALLY_OUT_OF_SCOPE` unless a later explicit contract rule establishes
that consequence.
