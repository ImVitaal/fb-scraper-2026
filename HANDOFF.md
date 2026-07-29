# Project handoff

**Date:** 2026-07-29  
**Branch:** `main`  
**Baseline commit:** `6a8acfb` (`feat: add repeatable configuration and metrics foundation`)

## Completion estimate

**Estimated overall completion: 25%.**

This is an implementation estimate, not an exit-gate result.

| Scope | State | Estimate |
|---|---|---:|
| Phase 1 — one Group | Partly implemented; exit gate open | 50% |
| Phase 2 — ten Groups | Not started | 0% |
| Phase 3 — competitor proof | Not started | 0% |

The full project completes only when every Phase 1, Phase 2, and Phase 3 gate
in `LEAN_THREE_PHASE_COMPLETION_PLAN.md` has current evidence.

## Verified current state

Executed at commit `6a8acfb`:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

- Ruff format: passed.
- Ruff lint: passed.
- `ty`: passed.
- Tests: 67 passed.
- Coverage: 81.08%.
- Working tree: clean.

## Delivered behavior

### Phase 1A

- Fixture-backed raw gzip storage outside the repository.
- SHA-256 verification, SQLite persistence, deterministic offline replay.
- CSV, JSON, SQLite, manifest, and Markdown outputs.

### Phase 1B

- Imported and guided-login Playwright storage-state workflows.
- Windows user-bound DPAPI envelope, inspect, and delete.
- Direct URL and CSV target selection.
- Strict fixture-backed keyword-and-location discovery parsing and selection.

### Phase 1C

- Strict fixture-backed Group, Post, media, and top-level Comment parsing.
- Raw-first single-page live capture with 30-day post filtering.
- Durable run state, interruption/resume fixture test, parser-drift failure receipt.
- Deterministic cursor-pagination helper with bounds and repeat-cursor detection.

### Phase 1D

- `pgscan inspect`, `resume`, `replay`, and dry-run-by-default `clean`.
- Retention cleanup receipts.
- Repeatable fixture-run TOML mode:

```toml
[run]
fixture = "fixture.json"
output = "operator-data"
raw_root = "../private-raw"
```

- Timing, CPU, sampled memory, storage, and completeness-adjusted throughput primitives.

## Open work, in order

1. Integrate the pagination helper into the Playwright adapter and live workflow.
   Raw page persistence and checkpointing must occur before each browser pagination action.
2. Add controlled browser-facing discovery and Group-layout adapters.
   Current live and discovery parsers accept strict synthetic marker layouts only.
3. Wire measurements into CLI runs and exports. Report counts, timings, retries,
   CPU, memory, and storage in receipts.
4. Run one controlled Group through imported and guided session workflows.
   Record hashes, command lines, counts, interruption/replay results, and limitations
   in the Phase 1 completion report.
5. Complete the Phase 1 exit-gate measurement suite: required-field accuracy,
   pagination completeness, duplicate rate, secret scan, and controlled workflow evidence.
6. Implement Phase 2 sequential ten-Group fixture workload, failure isolation,
   resume, measured baseline, bounded concurrency, and completion report.
7. Implement Phase 3 frozen competitor workload, import harness, three repeated
   runs per tool, receipts, and comparison report.
8. Perform a requirement-by-requirement completion audit before declaring completion.

## Important implementation limits

- `PlaywrightGroupCaptureAdapter` currently captures one rendered page.
- `LiveCaptureWorkflow` currently consumes one HTML page per call.
- The pagination helper exists but is not yet connected to browser navigation.
- Phase 2 and Phase 3 have no product implementation or run evidence.
- No controlled operator-visible Group run is recorded.

## Key paths

- Plan: `LEAN_THREE_PHASE_COMPLETION_PLAN.md`
- Phase log: `docs/phase-1/phase-1-log.md`
- CLI: `src/app/cli/main.py`
- Live capture: `src/app/workflows/live_capture.py`
- Browser adapter: `src/app/capture/playwright_adapter.py`
- Pagination: `src/app/capture/pagination.py`
- Metrics: `src/app/metrics.py`
- Session encryption: `src/app/session/dpapi.py`, `src/app/session/profiles.py`
- Tests: `tests/`

## Immediate continuation command

```powershell
Set-Location "C:\Users\teqhv\fb scraper"
uv run pytest
```

Then implement the first open work item above. Do not start Phase 2 until the
Phase 1 exit gate passes.
