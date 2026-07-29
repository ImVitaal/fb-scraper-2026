# Private Group Scanner — Phase 1 agent execution plan

> **Execution note:** `LEAN_THREE_PHASE_COMPLETION_PLAN.md` supersedes this
> document for current delivery. Keep this plan as a detailed historical
> reference.

**Revision:** 3
**Date:** 2026-07-29
**Status:** Decision-complete implementation source
**Goal:** Prove one correct, replayable, resumable private-Group workflow on native Windows.

## Source-of-truth order

Read these files before taking a work item:

1. `AGENTS.md`
2. `README.md`
3. `FACEBOOK_PRODUCT_DISCOVERY_ANSWERS.md`
4. `PHASE_1_OPTIMAL_PLAN.md`
5. `PHASE_1_CRITICAL_REVIEW.md`
6. `TOP_GITHUB_FACEBOOK_SCRAPERS_ARCHITECTURE_ANALYSIS.md`

Use the other research documents as supporting evidence.

When documents conflict, this plan controls Phase 1 implementation.

## Four-phase programme

| Phase | Purpose | Exit gate |
|---|---|---|
| 1 | One-Group correctness | One complete discovery-to-export demo passes fixture, replay, and resume gates |
| 2 | Ten-Group performance | Ten-Group workloads complete reliably with measured resource and throughput receipts |
| 3 | Competitor proof | Repeated equal-contract comparisons support explicit speed, efficiency, and cost conclusions |
| 4 | Product expansion | Proven private-Group core supports selected additional surfaces and intelligence workflows |

This document plans Phase 1 only.

## Phase 1 outcome

The guided command must complete one vertical slice:

```powershell
SAMPLE run
```

It must:

1. Prepare an imported browser session or guided-login session.
2. Accept a keyword and location.
3. Discover Groups visible through that session.
4. Let the operator select one Group.
5. Capture Group metadata.
6. Capture posts published during the previous 30 days.
7. Capture every visible top-level comment on those posts.
8. Store raw captures before parsing.
9. Normalize records into SQLite.
10. Export CSV, JSON, a manifest, and a Markdown report.
11. Resume safely after interruption.
12. Replay stored captures without network access.

Correctness and resume behavior gate Phase 1. Performance is instrumented but
has no release threshold.

## Scope

### Include

- CPython 3.12 on native Windows.
- A `src/` package layout.
- A guided CLI with optional TOML configuration.
- Free, self-hosted operation.
- No required paid dependency.
- Equal first-class imported-session and guided-login preparation.
- Windows user-bound encryption for stored session material.
- Session-aware keyword-and-location Group discovery.
- Direct URL and CSV target fallbacks.
- One selected Group in the live completion demo.
- Group metadata.
- Posts from the previous 30 days.
- All visible top-level comments on matching posts.
- Media metadata and source URLs.
- SQLite state, records, and observations.
- Gzip-compressed raw captures.
- SHA-256 integrity hashes.
- CSV, JSON, manifest, and Markdown outputs.
- Explicit job, session, and collection-health states.
- Deterministic raw-capture replay.
- Manual execution.
- Thirty-day private raw-capture retention.
- Ninety-day normalized-data retention.

### Defer

- Comment replies.
- Member export.
- More than one Group in the completion demo.
- Performance optimization and thresholds.
- Competitor selection and comparison.
- Scheduling.
- Pages, Events, profiles, advertisements, and Marketplace.
- Public HTTP API and dashboard.
- Discovery saturation, query evolution, semantic search, and local AI.

## Fixed technology choices

| Concern | Phase 1 choice |
|---|---|
| Runtime | CPython 3.12 |
| Package and dependency manager | `uv` |
| Build backend | `uv_build` |
| Package layout | `src/` |
| CLI | Typer |
| Schemas | Pydantic v2 |
| Browser capture | Playwright for Python |
| HTML parsing | BeautifulSoup 4 with `lxml` |
| Database | Python `sqlite3` |
| Migrations | Ordered SQL files plus schema-version table |
| Raw compression | `gzip` |
| Integrity | SHA-256 through `hashlib` |
| Session encryption | Windows Data Protection API |
| Configuration | TOML through `tomllib` |
| Tests | Pytest, pytest-cov, Hypothesis where useful |
| Lint and format | Ruff |
| Type checking | `ty` |
| Security checks | detect-secrets and pip-audit |

Commit `uv.lock`. Use dependency groups for development tools.

## Operator interfaces

### Session preparation

```powershell
SAMPLE session import
SAMPLE session login
SAMPLE session inspect
SAMPLE session delete
```

Both preparation paths must produce the same encrypted session envelope.

Imported-session behavior:

- Detect supported installed browsers.
- Let the operator select a local profile.
- Copy only required session material into the encrypted application store.
- Record source browser, import time, and health without recording secret values.

Guided-login behavior:

- Open a visible isolated browser window.
- Let the operator enter credentials directly into the source login page.
- Detect successful session establishment.
- Persist only encrypted session material.
- Never capture, log, or store passwords.

### Guided run

```powershell
SAMPLE run
```

Prompt for:

1. Session profile.
2. Keyword.
3. Location.
4. Maximum candidate count.
5. Selected Group.
6. History window, default 30 days.
7. Output directory.

Before execution, print:

- Exact discovery query.
- Session health class without secrets.
- Candidate count.
- Selected Group count.
- UTC history boundary.
- Maximum pagination interactions.
- Output path.

### Repeatable run

```powershell
SAMPLE run --config examples/campaign.toml --non-interactive
```

The configuration stores a session-profile identifier, never session secrets.

### Operations

```powershell
SAMPLE inspect RUN_ID
SAMPLE resume RUN_ID
SAMPLE replay RUN_ID --offline
SAMPLE clean --raw-older-than 30d --normalized-older-than 90d --dry-run
SAMPLE clean --raw-older-than 30d --normalized-older-than 90d
```

## Adapter boundaries

Implement these adapters:

1. **Fixture discovery adapter** for deterministic tests.
2. **Session-aware Group discovery adapter** for keyword-and-location search.
3. **Manual target adapter** for direct URLs and CSV.
4. **Browser session adapter** for imported and guided-login sessions.
5. **Private Group capture adapter** for metadata, posts, and comment expansion.
6. **Replay adapter** that performs no network requests.

Every adapter must expose capabilities, plan deterministic units, return raw
captures, classify results, and report its version.

Adapters must not write normalized records. Parsers must not schedule retries.
The CLI must not manipulate browser selectors.

## Data contracts

### Group

- `group_id`
- `canonical_url`
- `name`
- `privacy`
- `membership_state`
- `description`
- `member_count`
- `observed_at`
- `availability`

### Post

- `post_id`
- `group_id`
- `canonical_url`
- `author_id`
- `author_name`
- `published_at`
- `observed_at`
- `text`
- `post_type`
- `media`
- `reactions`
- `comments_count`
- `shares_count`
- `availability`

### Comment

- `comment_id`
- `post_id`
- `group_id`
- `parent_comment_id`, always null in Phase 1
- `author_id`
- `author_name`
- `published_at`
- `observed_at`
- `text`
- `media`
- `reactions`
- `availability`

Collect all visible top-level comments attached to qualifying posts, regardless
of comment publication time. Do not expand replies.

### Evidence envelope

Every normalized record must include:

- `schema_version`
- `adapter_name`
- `adapter_version`
- `parser_version`
- `collected_at`
- `raw_capture_id`
- `raw_sha256`
- `source_url`
- `session_class`
- `visibility_context`
- `field_provenance`
- `null_reasons`
- `collection_health`

Changing counters are timestamped observations. Never overwrite observation history.

## State vocabularies

### Work-item states

```text
planned
in_progress
blocked
review
complete
```

### Job states

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

```text
observed
unchanged
partial
unavailable
access_limited
membership_required
login_required
session_invalid
session_expired
session_challenged
session_restricted
temporarily_blocked
rate_limited
parser_drift
network_failed
```

An empty normalized result requires a non-success state unless the raw capture
explicitly proves a supported empty result.

## Persistence and security rules

SQLite must contain:

- Schema versions.
- Session-profile metadata without secrets.
- Discovery campaigns, queries, candidate hits, and ranks.
- Selected targets.
- Jobs, tasks, attempts, and failures.
- Raw-capture metadata.
- Pagination checkpoints.
- Group, Post, and Comment records.
- Counter observations.
- Export manifests.
- Cleanup and deletion receipts.

Before the next pagination interaction:

1. Store the current raw capture.
2. Verify and store its SHA-256 hash.
3. Commit normalized records.
4. Commit the next cursor or interaction checkpoint.
5. Mark the attempt durable.

Retries use stable idempotency keys derived from job, target, surface, expansion,
and cursor.

Session material must:

- Remain outside datasets, logs, fixtures, exports, and Git.
- Use Windows user-bound encryption at rest.
- Use restrictive local file permissions.
- Fail closed when decryption or integrity verification fails.
- Support explicit inspection and deletion.

Raw private captures must remain under the configured application data directory.
They must never enter the repository.

## Repository structure

```text
src/
  app/
    cli/
    sessions/
    discovery/
    adapters/
    capture/
    parsers/
    contracts/
    jobs/
    storage/
    exports/
tests/
  fixtures/
  unit/
  replay/
  integration/
  e2e/
migrations/
examples/
docs/
  phase-1/
    workitems/
    evidence/
pyproject.toml
uv.lock
README.md
SECURITY.md
CONTRIBUTING.md
```

## Agent operating contract

The root coordinator owns integration order, shared contracts, migrations, and
final verification.

Each delegated agent must receive one bounded work item containing:

- Work-item identifier and objective.
- Owned files or directories.
- Dependencies.
- Required skills.
- Required failing tests.
- Acceptance commands.
- Evidence output path.
- Explicit exclusions.

Agents must:

1. Read the source-of-truth files.
2. Confirm dependencies are complete.
3. Create or update the work-item record.
4. Write failing tests.
5. Implement the smallest complete behavior.
6. Run focused checks.
7. Simplify without weakening tests.
8. Write an evidence receipt.
9. Report changed files, commands, results, and remaining defects.

Agents must not:

- Modify files owned by another active work item.
- Change shared contracts or migrations without coordinator ownership.
- Mark work complete from status text alone.
- Use live private content in tests or commits.
- Store session material in fixtures.
- Broaden Phase 1 scope.

### Work-item record

Create `docs/phase-1/workitems/P1-XX.md` with:

```text
id
title
state
owner
dependencies
owned_paths
acceptance
commands
evidence_paths
changed_files
open_defects
```

### Evidence receipt

Create `docs/phase-1/evidence/P1-XX-receipt.md` containing:

- Commit or working-tree identifier.
- Exact commands.
- Tool versions.
- Test counts and results.
- Artifact paths and hashes.
- Acceptance-gate mapping.
- Limitations and open defects.

## Work breakdown

| ID | Work item | Dependencies | Completion evidence |
|---|---|---|---|
| P1-00 | Documentation and repository baseline | None | Clean baseline commit and aligned control documents |
| P1-01 | Python package, quality tools, CI, and skeleton | P1-00 | Install, lint, type, test, and build receipts |
| P1-02 | Contracts, states, migrations, and repositories | P1-01 | Schema tests and migration round-trip |
| P1-03 | Raw capture, hashing, retention, and offline replay | P1-02 | Byte-stable replay and cleanup receipts |
| P1-04 | Session envelope, DPAPI store, import, login, inspect, delete | P1-02 | Session contract tests and secret scan |
| P1-05 | Labelled Group, Post, Comment, and failure fixtures | P1-02 | Fixture manifest, hashes, and truth labels |
| P1-06 | Group, Post, and top-level Comment parsers | P1-03, P1-05 | Accuracy, mutation, and replay results |
| P1-07 | Fixture, session-aware discovery, and manual target adapters | P1-04, P1-05 | Discovery contract and health-state tests |
| P1-08 | Browser Group capture and pagination adapter | P1-03, P1-04, P1-05 | Capture contract, boundary, and cleanup tests |
| P1-09 | Durable jobs, checkpoints, retries, and resume | P1-02, P1-03, P1-06, P1-08 | Interruption matrix with identical final identifiers |
| P1-10 | Guided CLI, TOML mode, inspect, resume, replay, and cleanup | P1-07, P1-09 | CLI integration tests |
| P1-11 | Deterministic exports, manifest, report, and metrics | P1-06, P1-09 | Hash-stable export and metric tests |
| P1-12 | End-to-end fixture run and controlled one-Group demo | P1-10, P1-11 | Final offline and controlled demo receipts |
| P1-13 | Full verification, packaging, documentation, and closure | P1-12 | Final completion report |

## Execution waves

Use these dependency-safe waves:

1. **Foundation:** P1-00, then P1-01 and P1-02.
2. **Independent core lanes:** P1-03, P1-04, and P1-05.
3. **Collection lanes:** P1-06, P1-07, and P1-08.
4. **Orchestration:** P1-09.
5. **Operator and delivery lanes:** P1-10 and P1-11.
6. **Closure:** P1-12, then P1-13.

Run parallel agents only across independent lanes with disjoint owned paths.
The coordinator integrates each completed wave before releasing the next wave.

## Required skill sequence

Apply these skills to every implementation work item where relevant:

1. `modern-python`
2. `backend-patterns`
3. `tdd-workflow`
4. `python-testing`
5. `verification-loop`

Apply `insecure-defaults` to session, configuration, raw-capture, log, and export
paths. Apply code simplification only after tests pass.

## Test strategy

### Unit

- URL and identifier canonicalization.
- Date-boundary handling in UTC.
- State transitions.
- DPAPI envelope behavior through a replaceable protection interface.
- Hashing, compression, cleanup, and idempotency keys.
- Field extractors and null reasons.

### Replay

- Golden Group, Post, Comment, login, challenge, block, empty, and drift fixtures.
- Byte-stable normalized results for fixed versions.
- Mutated layouts that must report parser drift.
- Network-disabled enforcement.

### Integration

- Session profile to discovery adapter.
- Capture to raw store to parser to SQLite.
- Cursor commit and resume.
- Export parity across CSV, JSON, and SQLite.
- Retention cleanup with deletion receipts.

### End to end

- Fixture-backed guided workflow.
- Non-interactive TOML workflow.
- Intentional interruption during pagination.
- Offline replay.
- Controlled one-Group discovery-to-export demo.

## Deterministic release gates

- Required identifier precision: 100%.
- Supported required-field accuracy: at least 99%.
- Pagination completeness: at least 99.5%.
- Duplicate canonical records: at most 0.1%.
- Interrupted and uninterrupted final identifier sets: identical.
- Replay output hashes for fixed versions: identical.
- CSV, JSON, and SQLite identifier sets: identical.
- Error and health-state classification: 100%.
- Unsupported layouts reported as success: 0%.
- Session secrets in fixtures, logs, exports, or Git: 0.
- Package installation and guided fixture run on clean Windows: successful.

## Controlled demo gate

Use one operator-visible controlled Group.

The demo must:

1. Establish each session method in separate runs.
2. Discover the Group through keyword and location.
3. Select the Group from candidate results.
4. Collect the previous 30 days of posts.
5. Collect all visible top-level comments on those posts.
6. Record raw capture hashes without committing private content.
7. Interrupt one run after a durable checkpoint.
8. Resume to the same final identifier set.
9. Replay with network access disabled.
10. Produce every required output.

The receipt records counts, hashes, timings, resource use, health states, browser
version, adapter version, limitations, and failures. It contains no private
content or session secrets.

## Definition of done

Phase 1 is complete only when:

- Every work item is `complete`.
- Every evidence receipt exists.
- All deterministic release gates pass.
- The controlled demo gate passes.
- The package builds and installs on clean Windows.
- Security and contribution documents exist.
- CI runs Ruff, `ty`, Pytest, build, dependency audit, and secret detection.
- Raw captures remain outside Git.
- The final completion report contains the commit identifier, exact commands,
  test counts, build artifact hash, fixture version, demo limitations, deferred
  work, and open defects.

No Phase 2 performance work begins before this definition is satisfied.
