# Private Group Scanner — internal build brief

**Status:** Planning baseline
**Primary audience:** Technical operators and implementation agents
**Current milestone:** Phase 1 — one-Group correctness demo

## Mission

Build the fastest practical free local workflow for scanning posts and comments
from private Groups already visible to the operator.

The product must first prove correct, replayable, resumable collection. It will
optimize throughput after that proof exists. It will make no competitor
superiority claim before reproducible comparative evidence exists.

## Four-phase direction

### Phase 1 — One-Group correctness

Deliver one complete native-Windows vertical slice:

1. Prepare an imported browser session or a guided-login session.
2. Discover accessible Groups using a keyword and location.
3. Let the operator select one Group.
4. Collect posts published during the previous 30 days.
5. Collect every visible top-level comment on those posts.
6. Store raw captures before parsing.
7. Resume after an intentional interruption.
8. Replay stored captures without network access.
9. Export CSV, JSON, SQLite, a manifest, and a Markdown report.

Correctness and resume behavior gate completion. Speed is measured, not gated.

### Phase 2 — Ten-Group performance

Scale the proven workflow to ten Groups.

Add bounded concurrency, backpressure, workload classes, resource budgets, and
performance tuning. Measure posts per minute, comments per minute, end-to-end
duration, retries, CPU, memory, storage, and completeness-adjusted throughput.

### Phase 3 — Competitor proof

Select paid hosted competitors only after the local workflow is stable.

Freeze equal workloads and field contracts. Run repeated cold and warm tests.
Store receipts. Decide which speed, efficiency, completeness, and cost claims
the evidence supports.

### Phase 4 — Product expansion

Expand only after the private-Group advantage is proven.

Candidate additions include Pages, Events, profiles, advertisements,
Marketplace, scheduling, weekly intelligence, broader discovery, and advanced
analysis.

## Phase 1 product contract

### Included

- Native Windows.
- Python 3.12 or newer.
- One guided command-line workflow.
- Keyword-and-location Group discovery through the active session.
- Direct Group URL and CSV inputs as operational fallbacks.
- Equal first-class imported-session and guided-login preparation.
- One selected Group per demo run.
- Posts from the previous 30 days.
- All visible top-level comments on matching posts.
- Media metadata and source URLs without media downloads.
- Gzip raw captures with SHA-256 hashes.
- SQLite durable state and observations.
- CSV, JSON, manifest, and Markdown exports.
- Offline replay.
- Interrupted-run resume.
- Thirty-day private raw-capture retention.
- Ninety-day normalized-data retention.
- Zero required paid APIs, proxies, subscriptions, cloud services, or
  collection dependencies.

### Deferred

- Comment replies.
- More than one Group in the release demo.
- Performance thresholds.
- Competitor selection and comparison.
- Scheduling.
- Public Page and Event collection.
- Member export.
- Profiles, advertisements, and Marketplace.
- Dashboards, public APIs, local AI, and advanced intelligence.

## Intended operator workflow

```text
Prepare session
    ↓
Enter keyword and location
    ↓
Review accessible Group candidates
    ↓
Select one Group
    ↓
Review the 30-day boundary and collection limits
    ↓
Collect posts and top-level comments
    ↓
Inspect health, counts, and failures
    ↓
Export or resume
```

Both session methods must produce the same encrypted session contract.

- Imported session: read supported local browser session material.
- Guided login: open a controlled browser and let the operator complete login.
- Store only encrypted session material.
- Use Windows Data Protection API encryption for the current Windows user.
- Never store account passwords.
- Report invalid, expired, challenged, and restricted sessions explicitly.

## Architecture

```text
Guided CLI or TOML configuration
    ↓
Session preparation
    ↓
Session-aware Group discovery
    ↓
Operator target selection
    ↓
Durable job planner
    ↓
Browser capture adapter
    ↓
Gzip raw capture + SHA-256
    ↓
Group, Post, and Comment parsers
    ↓
Versioned contracts and provenance
    ↓
SQLite observations and checkpoints
    ↓
CSV + JSON + manifest + report
```

Discovery, authentication, transport, capture, parsing, normalization, storage,
and export must remain separate. Raw captures must exist before parsing.
Checkpoints must become durable before the next pagination interaction.

## Phase 1 completion gates

Phase 1 completes only when:

- Required identifier precision equals 100% on labelled fixtures.
- Supported required-field accuracy reaches at least 99%.
- Pagination completeness reaches at least 99.5% on labelled fixtures.
- Duplicate canonical records remain at or below 0.1%.
- Unsupported layouts never report successful collection.
- Offline replay produces deterministic normalized hashes.
- An interrupted run produces the same final identifier set as an uninterrupted run.
- Fixtures, logs, exports, and Git contain no session secrets.
- One controlled Group demo completes discovery, selection, collection, resume,
  replay, and every required export.
- The completion report includes exact commands, hashes, counts, limitations,
  and the commit identifier.

## Agent execution

`PHASE_1_OPTIMAL_PLAN.md` is the Phase 1 implementation source of truth.

Agents must:

1. Claim one bounded work item.
2. Respect its dependencies and file ownership.
3. Write failing tests before implementation.
4. Store verification evidence with the work item.
5. Report changed files and exact commands.
6. Mark work complete only after its acceptance gate passes.
7. Leave integration and shared-contract changes to the designated owner.

## Current repository state

The repository contains research and planning documents. No product package,
fixture corpus, migration, or working demo exists yet.

The previous Page-first Phase 1 direction is superseded by the current
private-Group-first plan.
