# FB Scraper 2026 — Phase 1 implementation plan

**Revision:** 2  
**Date:** 2026-07-29  
**Status:** Decision-complete implementation source  
**Goal:** Prove one reliable, replayable discovery-to-export workflow on native Windows.

## Fresh-session bootstrap

Read these files in order:

1. `AGENTS.md` — mandatory workflow and quality rules.
2. `FACEBOOK_PRODUCT_DISCOVERY_ANSWERS.md` — confirmed product decisions.
3. `PHASE_1_OPTIMAL_PLAN.md` — implementation source of truth.
4. `PHASE_1_CRITICAL_REVIEW.md` — reasons behind Revision 2 decisions.
5. `TOP_GITHUB_FACEBOOK_SCRAPERS_ARCHITECTURE_ANALYSIS.md` — reusable and rejected implementation patterns.
6. `NOVEL_COMPETITIVE_ADVANTAGE_FINDINGS.md` — future differentiation.

Use other research files only for supporting evidence.

When documents conflict, this plan takes precedence for Phase 1.

## Repository state

- Remote: `https://github.com/ImVitaal/fb-scraper-2026`
- Visibility: private.
- Remote content at planning time: empty.
- Local workspace: `C:\Users\teqhv\fb scraper`
- Local workspace at planning time: research files only; not Git-initialized.

Begin implementation by:

1. Initializing the current workspace as a `main` Git repository.
2. Adding the GitHub remote as `origin`.
3. Committing the research and planning documents.
4. Pushing the documentation baseline.
5. Creating an implementation branch from that baseline.

Do not delete or rewrite the research documents.

## Phase 1 outcome

The command below must complete one vertical slice:

```powershell
fbintel run
```

It must:

1. Accept a keyword and location.
2. Discover candidate Facebook Pages.
3. Allow the operator to select targets.
4. Capture Page metadata and Posts from the previous 30 days.
5. Store raw captures before parsing.
6. Normalize observations into SQLite.
7. Export CSV, JSON, a manifest and a Markdown report.
8. Resume safely after interruption.
9. Replay stored captures without new collection.

## Scope

### Include

- Python 3.12 on native Windows.
- One guided CLI with optional TOML configuration.
- Free, self-hosted operation.
- No paid collection dependency.
- Page discovery from keywords and locations.
- Manual Page URL and CSV fallback input.
- Public Page metadata.
- Public Page Posts from the previous 30 days.
- Media metadata and source URLs.
- SQLite job and observation storage.
- Gzip-compressed raw captures.
- SHA-256 integrity hashes.
- CSV, JSON, manifest and Markdown outputs.
- Explicit job and collection-health states.
- Deterministic raw-capture replay.
- Manual execution.
- Configurable 90-day retention.

### Defer

- Groups and cookie import.
- Events.
- Comments and replies.
- Personal profiles.
- Marketplace.
- Advertisements.
- Scheduling.
- Discovery Saturation Estimation.
- Message Family Query Expansion.
- Semantic search.
- Local AI.
- Public HTTP API.
- Dashboard.

## Fixed technology choices

| Concern | Phase 1 choice |
|---|---|
| Runtime | CPython 3.12 |
| Package layout | `src/` layout |
| CLI | Typer |
| Schemas | Pydantic v2 |
| Browser capture | Playwright for Python |
| HTML parsing | BeautifulSoup 4 with `lxml` |
| Database | Python `sqlite3` |
| Migrations | Ordered SQL files with a schema-version table |
| Raw compression | `gzip` |
| Hashing | SHA-256 through `hashlib` |
| Configuration | TOML through `tomllib` |
| Tests | Pytest |
| HTTP fixture support | `httpx` only where browser capture is not required |
| Lint and format | Ruff |
| Type checking | Pyright |
| Build backend | Hatchling |

Pin direct dependencies in `pyproject.toml`. Commit the resolved lock file.

## Initial adapters

### 1. Fixture discovery adapter

Purpose:

- Deterministic unit and end-to-end tests.
- Release-gate evidence.
- Offline development.

Input:

- Versioned JSON fixtures containing query, location, results, ranks and source health.

### 2. DuckDuckGo HTML discovery adapter

Purpose:

- Best-effort free live discovery.

Query shape:

```text
site:facebook.com KEYWORD LOCATION
```

Requirements:

- Store the exact query and retrieval timestamp.
- Preserve result rank and displayed URL.
- Reject obvious post, photo, login, share and redirect URLs when discovering Pages.
- Canonicalize Facebook Page URLs.
- Classify blocks, empty results and parser failures separately.
- Never interpret an empty response as no matching Pages.

The adapter is experimental. Its live result count is not a Phase 1 release gate.

### 3. Manual discovery adapter

Accept:

- One or more Page URLs.
- CSV containing a `url` column.

This is the operational fallback when live search is unhealthy.

### 4. Playwright public Page capture adapter

Purpose:

- Capture logged-out public Page metadata and recent public Posts.

Requirements:

- Use an isolated browser context.
- Store HTML and relevant structured response bodies when observed.
- Store source URL, retrieval time, response state and browser version.
- Stop at the 30-day boundary.
- Persist pagination state before the next interaction.
- Avoid downloading full media files.
- Close browser resources deterministically.

### 5. Replay adapter

Purpose:

- Feed stored raw captures through current or selected parser versions.
- Perform no network requests.
- Produce deterministic normalized output for the same inputs and versions.

## Architecture

```text
Guided CLI or TOML configuration
    ↓
Discovery campaign
    ↓
Candidate receipts
    ↓
Operator selection
    ↓
Durable job planner
    ↓
Playwright capture adapter
    ↓
Gzip raw capture + SHA-256
    ↓
Page and Post parsers
    ↓
Versioned Pydantic contracts
    ↓
SQLite observations and checkpoints
    ↓
CSV + JSON + manifest + report
```

## Repository structure

```text
fb-scraper-2026/
├── src/fbintel/
│   ├── cli/
│   ├── discovery/
│   ├── adapters/
│   ├── capture/
│   ├── parsers/
│   ├── contracts/
│   ├── jobs/
│   ├── storage/
│   └── exports/
├── tests/
│   ├── fixtures/
│   ├── unit/
│   ├── replay/
│   ├── integration/
│   └── e2e/
├── migrations/
├── examples/
│   └── campaign.toml
├── docs/
├── pyproject.toml
├── README.md
├── SECURITY.md
├── CONTRIBUTING.md
└── .gitignore
```

## State vocabularies

### Job states

Use only:

```text
planned
running
partial
succeeded
failed
interrupted
cancelled
```

### Collection-health states

Use only:

```text
observed
unchanged
partial
unavailable
access_limited
login_required
temporarily_blocked
rate_limited
parser_drift
network_failed
```

Empty normalized output requires a non-success health state unless the raw capture explicitly proves an empty supported result.

## Required contracts

### Page

- `page_id`
- `canonical_url`
- `name`
- `username`
- `category`
- `description`
- `website`
- `emails`
- `phones`
- `followers`
- `likes`
- `profile_image_url`
- `cover_image_url`
- `observed_at`
- `availability`

### Post

- `post_id`
- `page_id`
- `canonical_url`
- `published_at`
- `observed_at`
- `text`
- `post_type`
- `media`
- `reactions`
- `comments_count`
- `shares_count`
- `availability`

### Evidence envelope

Every record must include:

- `schema_version`
- `adapter_name`
- `adapter_version`
- `parser_version`
- `collected_at`
- `raw_capture_id`
- `raw_sha256`
- `source_url`
- `field_provenance`
- `null_reasons`
- `collection_health`

Changing counters must be stored as timestamped observations. Do not overwrite history.

## Persistence rules

SQLite must contain:

- Schema versions.
- Discovery campaigns.
- Discovery probes.
- Candidate hits and ranks.
- Selected targets.
- Jobs and attempts.
- Raw-capture metadata.
- Pagination checkpoints.
- Page records.
- Post records.
- Counter observations.
- Failures.
- Export manifests.

Before requesting the next page:

1. Commit all normalized records from the current capture.
2. Commit the current capture identifier and hash.
3. Commit the next cursor or interaction checkpoint.
4. Mark the attempt durable.

Retries must use stable idempotency keys derived from job, target, surface and cursor.

## CLI behavior

### Guided mode

```powershell
fbintel run
```

Prompts for:

1. Keyword.
2. Location.
3. Maximum candidate count.
4. Selected Page targets.
5. History window, default 30 days.
6. Output directory.

Before execution, print:

- Exact queries.
- Candidate count.
- Selected target count.
- History boundary.
- Planned maximum pages or interactions.
- Output path.

### Repeatable mode

```powershell
fbintel run --config examples/campaign.toml --non-interactive
```

The example configuration must contain every value required to execute without prompts.

### Replay

```powershell
fbintel replay RUN_ID
```

### Resume

```powershell
fbintel resume RUN_ID
```

### Inspect

```powershell
fbintel inspect RUN_ID
```

### Cleanup

```powershell
fbintel clean --older-than 90d --dry-run
fbintel clean --older-than 90d
```

## Output contract

```text
output/RUN_ID/
├── pages.csv
├── posts.csv
├── media.csv
├── observations.csv
├── failures.csv
├── data.json
├── manifest.json
└── report.md
```

`manifest.json` must contain:

- Run identifier.
- Start and finish times.
- Inputs and query fingerprints.
- Adapter, parser and schema versions.
- History boundary.
- Record counts.
- Success, partial and failure counts.
- Output file SHA-256 hashes.
- Raw-capture count.
- Resume events.
- Replay source run when applicable.

## Implementation sequence

1. Initialize Git and push the documentation baseline.
2. Create the Python package, quality tools and CI.
3. Define contracts, states and migrations.
4. Implement raw-capture storage, hashing and replay.
5. Build labelled, redacted Page and Post fixtures.
6. Implement parsers against fixtures.
7. Implement fixture and manual discovery adapters.
8. Implement DuckDuckGo HTML discovery as experimental.
9. Implement the Playwright public Page capture adapter.
10. Add durable jobs, checkpoints and idempotent writes.
11. Implement guided and TOML CLI modes.
12. Implement deterministic exports and reports.
13. Run the verification and packaging gates.

## Required skill sequence

1. `modern-python`
2. `backend-patterns`
3. `tdd-workflow`
4. `python-testing`
5. `verification-loop`

Apply `insecure-defaults` to raw captures, logs, configuration and export handling.

## Deterministic release gates

Evaluate these against labelled fixtures with fixed expected identifier sets:

- Required identifier precision: 100%.
- Required-field accuracy: at least 99%.
- Pagination completeness: at least 99.5%.
- Duplicate canonical records: at most 0.1%.
- Interrupted-run final identifier set: identical to uninterrupted execution.
- Replay output hashes: identical for the same capture and parser version.
- CSV and JSON identifier sets: identical.
- Error and health-state classification: 100%.
- Unsupported layouts reported as success: 0%.
- Secret values present in fixtures, logs or exports: 0.
- Clean Windows installation and guided run: successful.

## Live smoke tests

Live tests are observational and do not determine fixture accuracy percentages.

Run:

1. One keyword-and-location discovery.
2. One manual Page URL fallback.
3. One public Page capture.
4. One interruption and resume.
5. One replay with networking disabled.

Record:

- Source URLs.
- Timestamps.
- Candidate and record counts.
- Collection-health states.
- Browser and adapter versions.
- Failures and limitations.

Do not require a minimum live candidate or Post count.

## Definition of done

Phase 1 is complete only when the repository contains:

- Installable package.
- Guided and non-interactive CLI.
- SQLite migrations.
- Redacted fixture corpus.
- Unit, replay, integration and end-to-end tests.
- Windows installation instructions.
- Security and contribution documents.
- CI checks for Ruff, Pyright, Pytest and package build.
- One deterministic end-to-end receipt.
- One dated live smoke-test receipt.
- One replay receipt with networking disabled.

The final completion report must include:

- Commit SHA.
- Exact commands executed.
- Test counts and results.
- Package build path and hash.
- Fixture corpus version.
- Live smoke-test limitations.
- Open defects and deferred work.

## Phase 2 gate

Proceed to Groups and Events only after every deterministic release gate passes.

Phase 2 order:

1. Windows DPAPI-backed cookie import.
2. User-accessible Group capture.
3. Public Event capture.
4. Weekly snapshot comparison.
5. Discovery Saturation Estimation.
6. Message Family Query Expansion.

