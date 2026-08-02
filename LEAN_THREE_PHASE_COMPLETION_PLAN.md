# Private Group Scanner — lean three-phase completion plan

**Revision:** 1
**Date:** 2026-07-29
**Status:** Completed fixture-release plan
**Scope:** Completed fixture work for Phases 1, 2, and 3.

## Objective

Deliver working product behavior before adding more framework code.

Preserve the accepted P1-00 through P1-02 foundation. Change it only when a
failing workflow test proves that a correction is necessary.

| Phase | Outcome | Exit proof |
|---|---|---|
| 1 | One correct private-Group workflow | One Group completes session, discovery, capture, resume, replay, and export |
| 2 | Reliable ten-Group operation | Ten Groups complete with measured resource use and no record loss |
| 3 | Reproducible competitor proof | Equal-workload results support explicit claims |

## Lean rules

1. Keep one active milestone.
2. Demonstrate operator-visible behavior after every milestone.
3. Add abstractions only after two real implementations need them.
4. Add fields and tables only when the active workflow uses them.
5. Test product behavior, data integrity, and reproduced defects.
6. Keep one running log and one completion report per phase.
7. Use synthetic fixtures in Git.
8. Keep private captures and session material outside Git.
9. Measure before optimizing.
10. Stop refactoring accepted infrastructure unless it blocks the active slice.

Keep Python 3.12, `uv`, Ruff, `ty`, Pytest, `pgscan`, SQLite, and the accepted
contracts. Do not add another database, queue, API, dashboard, plugin framework,
cloud service, AI feature, or Phase 4 surface.

---

# Phase 1 — one-Group completion

## 1A — offline vertical slice

Build one fixture-backed workflow before browser work.

Implement:

- Gzip raw capture storage outside the repository.
- SHA-256 creation and verification.
- One Group, Post, and top-level Comment parser fixture.
- SQLite persistence.
- Offline replay.
- JSON and CSV exports.
- One CLI path through the complete slice.

Gate:

```powershell
pgscan run --fixture FIXTURE_PATH --output OUTPUT_PATH
pgscan replay RUN_ID --offline
```

Both commands must produce the same canonical identifier set.

## 1B — session and target preparation

Implement:

- Imported browser-session preparation.
- Guided visible login.
- One Windows user-bound encrypted session envelope.
- Session inspect and delete.
- Keyword-and-location Group discovery.
- Direct URL and CSV fallbacks.
- One selected Group.

Gate:

- Both session methods produce the same non-secret metadata contract.
- Passwords never enter storage or logs.
- Discovery or a fallback input selects one Group.

## 1C — live capture and resume

Implement:

- Group metadata.
- Posts from the previous 30 days.
- Every visible top-level Comment on matching Posts.
- Media metadata and source URLs.
- Raw capture before parsing.
- A durable checkpoint before each next-page interaction.
- Stable idempotency keys.
- Explicit health states.
- Interruption and resume.

Gate:

- Interrupted and uninterrupted fixture runs have identical identifiers.
- Unsupported layouts never report success.
- One controlled operator-visible Group completes capture.

## 1D — operator delivery

Implement:

- Guided `pgscan run` and repeatable TOML mode.
- `inspect`, `resume`, `replay`, and `clean`.
- CSV, JSON, SQLite, manifest, and Markdown outputs.
- Thirty-day raw and ninety-day normalized retention.
- Cleanup receipts.
- Counts, timings, retries, CPU, memory, and storage measurements.

Gate:

- Every output has the same canonical identifiers.
- Replay is deterministic.
- Cleanup respects dry-run and retention boundaries.

## 1E — controlled completion

Run one controlled Group through both session methods.

Record exact commands, commit, versions, non-private hashes, counts, interruption
results, replay results, export hashes, and limitations.

### Phase 1 exit gate

- Identifier precision is 100% on labelled fixtures.
- Supported required-field accuracy is at least 99%.
- Pagination completeness is at least 99.5%.
- Duplicate canonical records are at most 0.1%.
- Interrupted and uninterrupted identifiers match.
- Unsupported layouts produce zero false successes.
- Session secrets in Git, fixtures, logs, and exports equal zero.
- Both session methods complete the one-Group workflow.

Do not optimize throughput during Phase 1.

---

# Phase 2 — ten-Group reliability

## 2A — sequential baseline

- Accept up to ten selected Groups.
- Reuse the Phase 1 workflow unchanged.
- Isolate Group failures.
- Resume each Group independently.
- Record per-Group and total metrics.

Gate: ten fixture Groups complete sequentially. Injected failures do not lose
completed Groups. Resume matches uninterrupted results.

## 2B — bounded concurrency

Add concurrency only after measuring the sequential baseline.

- Use one configurable worker limit.
- Serialize session interactions when required.
- Add backpressure for raw writes and parsing.
- Enforce time, retry, memory, CPU, and storage budgets.
- Preserve graceful interruption.

Gate: concurrency improves measured time without reducing completeness or
increasing duplicates. Remove it if it provides no useful improvement.

## 2C — completion run

Run one warm-up fixture workload, two measured fixture workloads, and one
controlled operator-visible ten-Group workload.

### Phase 2 exit gate

- All ten Groups reach explicit terminal states.
- Successful Groups retain Phase 1 correctness.
- Failed Groups have actionable health and failure records.
- Resume matches uninterrupted results.
- Metrics include completeness-adjusted throughput.
- The report identifies the best safe worker limit.

Do not add new content surfaces during Phase 2.

---

# Phase 3 — competitor proof

## 3A — freeze the comparison

Select at most two competitors that can run the equivalent private-Group
workload.

Freeze:

- The same ten Groups and history boundary.
- The same Post and top-level Comment contract.
- The same required identifiers and fields.
- The same completion, failure, start, and stop definitions.

Exclude tools that cannot satisfy the frozen workload.

## 3B — comparison harness

- Import competitor exports without changing their values.
- Map comparable fields into one analysis table.
- Record missing and unsupported fields.
- Calculate completeness, duplicates, duration, throughput, retries, and cost.
- Store input hashes and run metadata.

Do not build permanent competitor adapters.

## 3C — repeated runs and report

Run one cold and two warm workloads for each tool. Preserve receipts, hashes,
failures, and exclusions.

### Phase 3 exit gate

- Every included tool used the frozen workload.
- Every result traces to input and output hashes.
- The report includes completeness-adjusted throughput and observed cost.
- Claims separate measured facts from interpretation.
- The report states where the local tool wins, ties, or loses.

Publish no superiority claim without supporting repeated results.

---

# Minimal documentation

Maintain only:

- This plan.
- One running log per phase.
- One completion report per phase.
- Setup, operation, security, and retention instructions.

Before adding architecture, identify the active milestone, failing test or
measured bottleneck, rejected smaller solution, and operator-visible benefit.
Skip the architecture when those answers are not concrete.

# Next execution source

Phases 1–3 now have fixture-backed completion receipts.

Use `docs/phase-4/PHASE_4_ONE_SHOT_THREAD_PM_PLAN.md` for the controlled Phase 4 operator release.
Do not start product expansion before its Phase 4 gate passes.
